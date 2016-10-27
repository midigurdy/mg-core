import logging
import os

from ._fluidsynth import lib, ffi

from mg.conf import settings


log = logging.getLogger('fluidsynth')

FS_LOG_LEVELS = {
    lib.FLUID_PANIC: 'critical',
    lib.FLUID_ERR: 'error',
    lib.FLUID_WARN: 'warning',
    lib.FLUID_INFO: 'info',
    lib.FLUID_DBG: 'debug'
}


@ffi.callback('void(int, char *, void *)')
def fs_log(level, message, _ignored):
    method = getattr(log, FS_LOG_LEVELS.get(level, 'error'))
    method(ffi.string(message))


class FluidSynthError(Exception):
    pass


class FluidSynth(object):
    def __init__(self, soundfont_dir=None, config={}):
        self.adriver = None
        self.synth = None
        self._ladspa = None
        self.soundfont_dir = settings.sound_dir
        self.soundfonts = {}
        self.channels = {}
        self.settings = lib.new_fluid_settings()
        self.configure(config)
        self.reverb = {
            'roomsize': 0.8,
            'damping': 0.01,
            'width': 0,
            'level': 0.01,
            'mode': 0,
        }
        self.set_logger()

    def set_logger(self):
        lib.fluid_set_log_function(lib.FLUID_PANIC, fs_log, ffi.NULL)
        lib.fluid_set_log_function(lib.FLUID_ERR, fs_log, ffi.NULL)
        lib.fluid_set_log_function(lib.FLUID_WARN, fs_log, ffi.NULL)
        lib.fluid_set_log_function(lib.FLUID_INFO, fs_log, ffi.NULL)
        lib.fluid_set_log_function(lib.FLUID_DBG, fs_log, ffi.NULL)

    def configure(self, config):
        for key, value in config.items():
            key = key.encode()
            ctype = lib.fluid_settings_get_type(self.settings, key)
            if ctype == lib.FLUID_STR_TYPE:
                value = str(value).encode()
                ret = lib.fluid_settings_setstr(self.settings, key, value)
            elif ctype == lib.FLUID_NUM_TYPE:
                ret = lib.fluid_settings_setnum(self.settings, key, float(value))
            elif ctype == lib.FLUID_INT_TYPE:
                ret = lib.fluid_settings_setint(self.settings, key, int(value))
            else:
                raise FluidSynthError('Unknown setting %s' % key)
            if ret != lib.FLUID_OK:
                raise FluidSynthError('Setting %s to %s failed (%s)!' % (key, value, ret))

    def load_font(self, filename):
        """
        Load a SoundFont file into FluidSynth and return the internal ID that
        FluidSynth uses to identify this font.
        """
        if filename not in self.soundfonts:
            path = os.path.join(self.soundfont_dir, filename)
            sfid = lib.fluid_synth_sfload(self.synth, path.encode(), 0)
            if sfid < 0:
                raise FluidSynthError('Unable to load soundfont "%s"' % path)
            self.soundfonts[filename] = sfid
        return self.soundfonts[filename]

    def unload_font(self, filename):
        sfid = self.soundfonts[filename]
        ret = lib.fluid_synth_sfunload(self.synth, sfid, 0)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to unload soundfont %s' % filename)
        del self.soundfonts[filename]

    def get_loaded_fonts(self):
        """
        Return a dict with key being the loaded soundfont filename,
        value the number of channels that this font is currently used on
        """
        used_ids = list(self.channels.values())
        return {filename: used_ids.count(sfid)
                for filename, sfid in self.soundfonts.items()}

    def unload_unused_soundfonts(self):
        for filename, count in self.get_loaded_fonts().items():
            if count == 0:
                self.unload_font(filename)
        log.info('%d soundfonts left after unloading' % lib.fluid_synth_sfcount(self.synth))

    def set_channel_sound(self, channel, font_filename, bank, program):
        sfid = self.load_font(font_filename)
        self.select_program(channel, sfid, bank, program)
        self.channels[channel] = sfid

    def clear_channel_sound(self, channel):
        if channel not in self.channels:
            return
        ret = lib.fluid_synth_unset_program(self.synth, channel)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to clear channel')
        del self.channels[channel]

    def clear_all_channel_sounds(self):
        for channel, sfid in self.channels.items():
            ret = lib.fluid_synth_unset_program(self.synth, channel)
            if ret != lib.FLUID_OK:
                log.error('Unable to clear channel sound %s', channel)
        self.channels = {}

    def set_channel_fine_tune(self, channel, value):
        """
        value range is +-100 (cent)
        """
        fine_tune = int((2**14 / 200.0) * (value + 100))
        if fine_tune < 0:
            fine_tune = 0
        elif fine_tune > 16383:
            fine_tune = 16383

        msb = fine_tune >> 7
        lsb = fine_tune & 0x7F

        # set RPN to fine tune
        lib.fluid_synth_cc(self.synth, channel, 101, 0)
        lib.fluid_synth_cc(self.synth, channel, 100, 1)

        # send data
        lib.fluid_synth_cc(self.synth, channel, 6, msb)
        lib.fluid_synth_cc(self.synth, channel, 38, lsb)

    def select_program(self, channel, font_id, bank, preset):
        ret = lib.fluid_synth_program_select(self.synth, channel, font_id, bank, preset)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to select program')

    def set_reverb(self, **kwargs):
        args = self.reverb
        args.update(kwargs)
        lib.fluid_synth_set_reverb(self.synth, args['roomsize'], args['damping'],
                                   args['width'], args['level'])

    def set_sympathetic_reverb(self, on):
        # FIXME!
        pass

    def set_channel_volume(self, channel, volume):
        self._send_cc(channel, 7, volume)

    def set_pitch_bend_range(self, channel, semitones):
        ret = lib.fluid_synth_pitch_wheel_sens(self.synth, channel, semitones)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to set pitch bend range')

    def get_cpu_load(self):
        return lib.fluid_synth_get_cpu_load(self.synth)

    def get_gain(self):
        return lib.fluid_synth_get_gain(self.synth)

    def set_gain(self, gain):
        lib.fluid_synth_set_gain(self.synth, float(gain))

    def start(self):
        if self.synth:
            raise FluidSynthError('Already started!')
        self.synth = lib.new_fluid_synth(self.settings)
        if not self.synth:
            raise FluidSynthError('Unable to create synthesizer')
        self.adriver = lib.new_fluid_audio_driver(self.settings, self.synth)
        if not self.adriver:
            raise FluidSynthError('Unable to create synth audio driver')

    def stop(self):
        if self.adriver:
            lib.delete_fluid_audio_driver(self.adriver)
            self.adriver = None
        if self.synth:
            lib.delete_fluid_synth(self.synth)
            self.synth = None
        if self.settings:
            lib.delete_fluid_settings(self.settings)
            self.settings = None

    def _send_cc(self, channel, ctrl, val):
        ret = lib.fluid_synth_cc(self.synth, channel, ctrl, val)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to set cc')

    @property
    def ladspa(self):
        if not self._ladspa:
            fx = lib.fluid_synth_get_ladspa_fx(self.synth)
            if not fx:
                raise FluidSynthError('LADSPA is not enabled!')
            self._ladspa = LADSPA(fx)
        return self._ladspa

    def __del__(self):
        self.stop()


class LADSPA:
    def __init__(self, fx):
        self.fx = fx

    def is_active(self):
        return lib.fluid_ladspa_is_active(self.fx)

    def activate(self):
        ret = lib.fluid_ladspa_activate(self.fx)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to activate LADSPA')

    def deactivate(self):
        ret = lib.fluid_ladspa_deactivate(self.fx)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to deactivate LADSPA')

    def reset(self):
        ret = lib.fluid_ladspa_reset(self.fx)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to reset LADSPA')

    def add_effect(self, name, library, plugin=None, mix=False, mix_gain=1.0):
        ret = lib.fluid_ladspa_add_effect(self.fx, name.encode(), library.encode(),
                                          plugin.encode() if plugin else ffi.NULL)
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to add effect %s' % name)
        if mix:
            ret = lib.fluid_ladspa_effect_set_mix(self.fx, name.encode(), 1, float(mix_gain))
            if ret != lib.FLUID_OK:
                raise FluidSynthError('Unable to set mix mode on %s' % name)

    def mix_effect(self, name, gain):
        ret = lib.fluid_ladspa_effect_set_mix(self.fx, name.encode(), 1, float(gain))
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to set mix gain on %s' % name)

    def link_effect(self, name, port1, port2):
        ret = lib.fluid_ladspa_effect_link(self.fx, name.encode(), port1.encode(),
                                           port2.encode())
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to link effect %s' % name)

    def set_control(self, name, port, value):
        ret = lib.fluid_ladspa_effect_set_control(self.fx, name.encode(),
                                                  port.encode(), float(value))
        if ret != lib.FLUID_OK:
            raise FluidSynthError('Unable to set control %s %s' % (name, port))
