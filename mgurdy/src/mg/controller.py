import json
import logging

import alsaaudio

from mg.conf import find_config_file
from mg.mglib import mgcore
from mg.signals import EventListener
from mg.input.midi import MidiInput

from . import utils


log = logging.getLogger('controller')


VOICE_MODES = (
    'midigurdy',
    'generic',
    'keyboard',
)


class SynthController(EventListener):
    events = [
        'key_on_debounce:changed',
        'key_off_debounce:changed',
        'base_note_delay:changed',
        'poly_base_note:changed',
        'poly_pitch_bend:changed',
        'sound:changed',
        'sound:deleted',
        'synth:gain:changed',
        'reverb_volume:changed',
        'reverb_panning:changed',
        'active:preset:voice:muted:changed',
        'active:preset:voice:volume:changed',
        'coarse_tune:changed',
        'pitchbend_range:changed',
        'fine_tune:changed',
        'multi_chien_threshold:changed',
        'active:preset:changed',
        'active:preset:voice:base_note:changed',
        'active:preset:voice:capo:changed',
        'active:preset:voice:sound:changed',
        'active:preset:voice:mode:changed',
        'active:preset:voice:polyphonic:changed',
        'active:preset:voice:panning:changed',
        'active:preset:voice:finetune:changed',
        'active:preset:voice:chien_threshold:changed',
        'active:preset:preload',
        'clear:preload',
        'string_count:changed',
    ]

    def __init__(self, fluid, state):
        self.fluid = fluid
        self.state = state

    def synth_gain_changed(self, gain, **kwargs):
        self.set_synth_gain(gain)

    def pitchbend_range_changed(self, pitchbend_range, **kwargs):
        mgcore.set_pitchbend_range(pitchbend_range)

    def key_on_debounce_changed(self, key_on_debounce, **kwargs):
        mgcore.set_key_on_debounce(key_on_debounce)

    def key_off_debounce_changed(self, key_off_debounce, **kwargs):
        mgcore.set_key_off_debounce(key_off_debounce)

    def base_note_delay_changed(self, base_note_delay, **kwargs):
        mgcore.set_base_note_delay(base_note_delay)

    def poly_base_note_changed(self, poly_base_note, **kwargs):
        mgcore.set_feature('poly_base_note', poly_base_note)

    def poly_pitch_bend_changed(self, poly_pitch_bend, **kwargs):
        mgcore.set_feature('poly_pitch_bend', poly_pitch_bend)

    def string_count_changed(self, string_count, **kwargs):
        mgcore.set_string_params(self.string_mute_configs())

    def reverb_volume_changed(self, reverb_volume, **kwargs):
        self.set_reverb_volume(reverb_volume)

    def reverb_panning_changed(self, reverb_panning, **kwargs):
        self.set_reverb_panning(reverb_panning)

    def active_preset_voice_muted_changed(self, **kwargs):
        mgcore.set_string_params(self.string_mute_configs())

    def active_preset_voice_volume_changed(self, volume, sender, **kwargs):
        self.set_voice_volume(sender, volume)

    def active_preset_voice_base_note_changed(self, **kwargs):
        mgcore.set_string_params(self.base_note_configs())

    def active_preset_voice_capo_changed(self, **kwargs):
        mgcore.set_string_params(self.melody_capo_configs())

    def active_preset_voice_sound_changed(self, sender, **kwargs):
        self.set_string_sound(sender)
        mgcore.set_string_params(self.string_mute_configs())

    def active_preset_voice_mode_changed(self, mode, sender, **kwargs):
        mgcore.set_string_params([(sender.string, 'mode', VOICE_MODES.index(sender.get_mode()))])

    def active_preset_voice_polyphonic_changed(self, polyphonic, sender, **kwargs):
        mgcore.set_string_params([(sender.string, 'polyphonic', int(sender.polyphonic))])

    def active_preset_voice_panning_changed(self, panning, sender, **kwargs):
        mgcore.set_string_params([(sender.string, 'panning', sender.panning)])

    def active_preset_voice_chien_threshold_changed(self, **kwargs):
        mgcore.set_string_params(self.chien_threshold_configs())

    def multi_chien_threshold_changed(self, **kwargs):
        mgcore.set_string_params(self.chien_threshold_configs())

    def coarse_tune_changed(self, **kwargs):
        mgcore.set_string_params(self.base_note_configs())

    def fine_tune_changed(self, **kwargs):
        for voice in self.state.preset.voices:
            self.set_voice_fine_tune(voice)

    def active_preset_voice_finetune_changed(self, sender, **kwargs):
        self.set_voice_fine_tune(sender)

    def set_voice_fine_tune(self, voice):
        fine_tune = voice.finetune + self.state.fine_tune
        self.fluid.set_channel_fine_tune(voice.channel, fine_tune)

    def active_preset_changed(self, **kwargs):
        self.configure_all_voices()
        self.set_synth_gain(self.state.synth.gain)
        mgcore.set_pitchbend_range(self.state.pitchbend_range)
        mgcore.set_string_params(self.chien_threshold_configs())
        self.set_reverb_volume(self.state.reverb_volume)
        self.set_reverb_panning(self.state.reverb_panning)

    def sound_changed(self, id, **kwargs):
        # if the changed sound is currently in use, clear all sounds
        # and then do a complete reconfiguration of the synth
        if id in self.fluid.get_loaded_fonts():
            self.configure_all_voices(clear_sounds=True)

    def sound_deleted(self, id, **kwargs):
        # if the deleted sound is currently in use, clear all sounds
        # and then do a complete reconfiguration of the synth
        if id in self.fluid.get_loaded_fonts():
            self.configure_all_voices(clear_sounds=True)

    def active_preset_preload(self, **kwargs):
        for voice in self.state.preset.voices:
            if not voice.get_sound():
                continue
            self.fluid.pin_sound(voice.soundfont_id, voice.bank, voice.program)

    def clear_preload(self, *kwargs):
        self.fluid.unpin_all_sounds()

    def configure_all_voices(self, clear_sounds=False):
        mgcore.halt_outputs()
        try:
            if clear_sounds:
                self.fluid.clear_all_channel_sounds()
                self.fluid.unload_unused_soundfonts()

            configs = []

            for voice in self.state.preset.voices:
                string = voice.string

                if voice.get_sound():
                    self.fluid.set_channel_sound(
                        voice.channel,
                        voice.soundfont_id,
                        voice.bank,
                        voice.program)
                    muted = voice.muted or voice.number > self.state.string_count
                    configs.append((string, 'mute', int(muted)))
                    configs.append((string, 'bank', voice.bank))
                    configs.append((string, 'program', voice.program))
                else:
                    self.fluid.clear_channel_sound(voice.channel)
                    configs.append((string, 'mute', 1))

                configs.append((string, 'volume', voice.volume))
                configs.append((string, 'panning', voice.panning))
                configs.append((string, 'mode', VOICE_MODES.index(voice.get_mode())))

                configs.append((string, 'base_note', self.get_effective_base_note(voice)))

                if voice.type == 'melody':
                    configs.append((string, 'capo', voice.capo))
                    configs.append((string, 'polyphonic', int(voice.polyphonic)))

            mgcore.set_string_params(configs)

            self.fluid.unload_unused_soundfonts()
        finally:
            mgcore.resume_outputs()

    def melody_capo_configs(self):
        configs = []
        for voice in self.state.preset.melody:
            configs.append((voice.string, 'capo', voice.capo))
        return configs

    def string_mute_configs(self):
        configs = []
        for voice in self.state.preset.voices:
            string = '%s%d' % (voice.type, voice.number)
            if not voice.get_sound():
                configs.append((string, 'mute', 1))
            else:
                muted = voice.muted or voice.number > self.state.string_count
                configs.append((string, 'mute', int(muted)))
        return configs

    def base_note_configs(self):
        configs = []
        for voice in self.state.preset.voices:
            configs.append((voice.string, 'base_note', self.get_effective_base_note(voice)))
        return configs

    def get_effective_base_note(self, voice):
        return voice.base_note + self.state.coarse_tune

    def chien_threshold_configs(self):
        configs = []
        for voice in self.state.preset.trompette:
            if self.state.multi_chien_threshold:
                threshold = voice.chien_threshold
            else:
                threshold = self.state.preset.trompette[0].chien_threshold
            threshold = int(5000 - (5000 * (threshold / 100.0)))
            configs.append((voice.string, 'chien_threshold', threshold))
        return configs

    def set_string_sound(self, voice):
        mgcore.set_string_params([(voice.string, 'mute', 1)])
        sound = voice.get_sound()
        if not sound:
            self.fluid.clear_channel_sound(voice.channel)
            return
        self.fluid.set_channel_sound(voice.channel, sound.soundfont.filename,
                                     voice.bank, voice.program)
        configs = [
            (voice.string, 'mode', VOICE_MODES.index(voice.get_mode())),
            (voice.string, 'bank', voice.bank),
            (voice.string, 'program', voice.program),
        ]

        muted = voice.muted or voice.number > self.state.string_count
        if not muted:
            configs.append((voice.string, 'mute', 0))
        mgcore.set_string_params(configs)
        self.set_voice_fine_tune(voice)

    def set_reverb_volume(self, volume):
        level = utils.scale(volume, 0, 100, 0.01, 1.0)
        if not volume:
            self.fluid.ladspa.deactivate()
        else:
            self.fluid.ladspa.mix_effect('sympa', level)
            if not self.fluid.ladspa.is_active():
                self.fluid.ladspa.activate()

    def set_reverb_panning(self, panning):
        self.fluid.ladspa.set_control('sympa', 'Wet Left', utils.balance2amp(panning, 'left'))
        self.fluid.ladspa.set_control('sympa', 'Wet Right', utils.balance2amp(panning, 'right'))

    def set_voice_volume(self, voice, volume):
        mgcore.set_string_params([(voice.string, 'volume', volume)])

    def set_synth_gain(self, gain):
        gain = (gain / (127 / 3.0))
        self.fluid.set_gain(gain)


class SystemController(EventListener):
    events = (
        'main_volume:changed',
        'ui:brightness:changed',
        'ui:string_group:changed',
        'ui:string_group_by_type:changed',
        'active:preset:changed',
        'active:preset:voice:muted:changed',
        'active:preset:voice:sound:changed',
    )

    def __init__(self, state, settings):
        self.state = state

        self.backlight_file = settings.backlight_control
        self.led_brightnes_file = (
            settings.led_brightness_3,
            settings.led_brightness_2,
            settings.led_brightness_1,
        )
        self.alsa_mixer_name = settings.alsa_mixer
        self.udc_config_file = settings.udc_config

        self.log = logging.getLogger('system')
        self._mixer = None

    def main_volume_changed(self, main_volume, **kwargs):
        self.set_volume(main_volume)

    def ui_brightness_changed(self, brightness, **kwargs):
        self.set_brightness(brightness)

    def ui_string_group_changed(self, **kwargs):
        self.update_string_leds()

    def ui_string_group_by_type_changed(self, **kwargs):
        self.update_string_leds()

    def active_preset_changed(self, **kwargs):
        self.update_string_leds()
        self.set_volume(self.state.main_volume)
        self.set_brightness(self.state.ui.brightness)

    def active_preset_voice_muted_changed(self, **kwargs):
        self.update_string_leds()

    def active_preset_voice_sound_changed(self, **kwargs):
        self.update_string_leds()

    def update_string_leds(self):
        voices = self.state.active_voice_list()
        for i in range(3):
            try:
                voice = voices[i]
                self.set_string_led(i, not voice.is_silent())
            except IndexError:
                self.set_string_led(i, 0)

    def set_string_led(self, string, on):
        try:
            with open(self.led_brightnes_file[string], 'w') as f:
                f.write('255' if on else '0')
        except Exception:
            self.log.exception('Unable to set string led')

    def get_brightness(self):
        try:
            with open(self.backlight_file, 'r') as f:
                val = int(f.read())
            return int(utils.scale(val, 0, 255, 0, 100))
        except Exception:
            self.log.exception('Unable to get brightness')
            return 0

    def set_brightness(self, val):
        try:
            val = int(utils.scale(val, 0, 100, 0, 255))
            with open(self.backlight_file, 'w') as f:
                f.write(str(val))
        except Exception:
            self.log.exception('Unable to set brightness')

    def set_volume(self, volume):
        try:
            if self.mixer:
                self.mixer.setvolume(utils.midi2percent(volume), alsaaudio.MIXER_CHANNEL_ALL)
        except Exception:
            self.log.exception('Unable to set main volume')

    @property
    def mixer(self):
        if self._mixer is None and self.alsa_mixer_name != 'disabled':
            self._mixer = alsaaudio.Mixer(self.alsa_mixer_name)
        return self._mixer

    def update_udc_configuration(self):
        try:
            with open(self.udc_config_file, 'r') as f:
                self.state.midi.udc_config = int(f.read())
        except Exception:
            self.log.exception('Unable to determine UDC config')


class MIDIController(EventListener):
    events = (
        'midi:port:removed',
        'midi:port:input_enabled:changed',
        'midi:port:output_enabled:changed',
        'midi:port:melody_channel:changed',
        'midi:port:drone_channel:changed',
        'midi:port:trompette_channel:changed',
        'midi:port:program_change:changed',
        'midi:port:speed:changed',
    )

    def __init__(self, input_manager):
        self.input_manager = input_manager

    def midi_port_removed(self, port_state, **kwargs):
        if port_state.output_enabled:
            mgcore.remove_midi_output(port_state.port.device)
        if port_state.input_enabled:
            self.input_manager.unregister(port_state.port.device)

    def midi_port_input_enabled_changed(self, input_enabled, sender, **kwargs):
        port_state = sender
        if input_enabled:
            self._add_midi_input(port_state.port)
        else:
            self.input_manager.unregister(port_state.port.device)

    def midi_port_output_enabled_changed(self, output_enabled, sender, **kwargs):
        port_state = sender
        if output_enabled:
            mgcore.add_midi_output(port_state.port.device)
            self._config_midi_output(port_state)
            mgcore.enable_midi_output(port_state.port.device)
        else:
            mgcore.remove_midi_output(port_state.port.device)

    def midi_port_melody_channel_changed(self, melody_channel, sender, **kwargs):
        self._config_midi_output(sender)

    def midi_port_drone_channel_changed(self, drone_channel, sender, **kwargs):
        self._config_midi_output(sender)

    def midi_port_trompette_channel_changed(self, trompette_channel, sender, **kwargs):
        self._config_midi_output(sender)

    def midi_port_program_change_changed(self, program_change, sender, **kwargs):
        self._config_midi_output(sender)

    def midi_port_speed_changed(self, speed, sender, **kwargs):
        self._config_midi_output(sender)

    def _config_midi_output(self, port_state):
        if port_state.output_enabled:
            mgcore.config_midi_output(
                device=port_state.port.device,
                melody_channel=port_state.melody_channel,
                trompette_channel=port_state.trompette_channel,
                drone_channel=port_state.drone_channel,
                program_change=port_state.program_change,
                speed=port_state.speed)

    def _add_midi_input(self, port):
        filename = find_config_file('midi.json')
        try:
            with open(filename, 'rb') as f:
                config = json.load(f)
        except Exception:
            log.exception('Unable to open midi device config')
            return
        config['device'] = port.device
        inp = MidiInput.from_config(config, port=port)
        self.input_manager.register(inp)
