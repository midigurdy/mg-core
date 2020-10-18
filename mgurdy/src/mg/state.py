from contextlib import contextmanager
import threading
import logging

from mg.signals import EventEmitter, signals
from mg.utils import PeriodicTimer
from mg.db import Preset, load_midi_config
from mg.sf2 import SoundFont
from mg.alsa.api import RawMIDI
from mg.mglib import mgcore


log = logging.getLogger('state')


STRING_TYPES = (
    {'name': 'drone', 'label': 'Drone', 'group': 1},
    {'name': 'melody', 'label': 'Melody', 'group': 0},
    {'name': 'trompette', 'label': 'Tromp', 'group': 2},
)

MOD_KEY_MODES = (
    'group_preset_next',
    'group_preset_prev',
    'preset_next',
    'preset_prev',
    'preset',
    'group_next',
    'group_prev',
    'group',
    'group1',
    'group2',
)


INSTRUMENT_MODES = {
    'simple_three': {
        'string_count': 1,
        'mod1_key_mode': 'preset_prev',
        'mod2_key_mode': 'preset_next',
        'wrap_presets': False,
        'wrap_groups': False,
        'string_group_by_type': False,
    },
    'simple_six': {
        'string_count': 2,
        'mod1_key_mode': 'preset',
        'mod2_key_mode': 'group_next',
        'wrap_presets': False,
        'wrap_groups': True,
        'string_group_by_type': False,
    },
    'nine_rows': {
        'string_count': 3,
        'mod1_key_mode': 'group_preset_prev',
        'mod2_key_mode': 'group_preset_next',
        'wrap_presets': False,
        'wrap_groups': False,
        'string_group_by_type': False,
    },
    'nine_cols': {
        'string_count': 3,
        'mod1_key_mode': 'preset',
        'mod2_key_mode': 'group',
        'wrap_presets': False,
        'wrap_groups': True,
        'string_group_by_type': True,
    },
    'old_mg': {
        'string_count': 3,
        'mod1_key_mode': 'group1',
        'mod2_key_mode': 'group2',
        'wrap_presets': False,
        'wrap_groups': False,
        'string_group_by_type': False,
    },
}


class State(EventEmitter):
    def __init__(self, settings):
        super().__init__()
        self._lock = threading.RLock()
        self._obj_path_cache = {}
        self._mod_levels = []

        with signals.suppress():
            self.preset = PresetState(prefix='active:preset')

            self.main_volume = 0
            self.reverb_volume = 0
            self.reverb_panning = 0
            self.coarse_tune = 0
            self.fine_tune = 0
            self.last_preset_number = 0
            self.pitchbend_range = 0

            self.key_on_debounce = 2
            self.key_off_debounce = 10
            self.base_note_delay = 20

            self.instrument_mode = 'simple_three'
            self.string_count = 1
            self.mod1_key_mode = 'preset_prev'
            self.mod2_key_mode = 'preset_next'
            self.wrap_presets = True
            self.wrap_groups = True
            self.multi_chien_threshold = False

            self.chien_sens_reverse = False

            self.poly_base_note = True
            self.poly_pitch_bend = True

            self.presets_preloaded = False

            self.ui = UIState()
            self.synth = SynthState()
            self.power = PowerState(
                ac_state_file=settings.power_state_ac,
                usb_state_file=settings.power_state_usb,
                battery_voltage_file=settings.battery_voltage,
            )

            self.midi = MIDIState()

    @contextmanager
    def lock(self, message=None, goto_home=False):
        self._lock.acquire()
        if message is not None:
            signals.emit('state:locked', {'message': message})
        try:
            yield
        finally:
            self._lock.release()
            if message is not None:
                signals.emit('state:unlocked', {'goto_home': goto_home})

    def attr_by_path(self, path):
        names = path.split('.')
        if len(names) > 1:
            obj = self.obj_by_path('.'.join(names[:-1]))
        else:
            obj = self
        if obj:
            return {'obj': obj, 'attr': names[-1]}

    def obj_by_path(self, path):
        cached = self._obj_path_cache.get(path)
        if cached is None:
            try:
                names = path.split('.')
                obj = self
                for name in names:
                    if name.isdigit():
                        obj = obj[int(name)]
                    else:
                        obj = getattr(obj, name)
                cached = obj
                self._obj_path_cache[path] = cached
            except Exception:
                log.exception('Unable to resolve obj path "{}"'.format(path))
        return cached

    def preload_presets(self):
        mgcore.halt_outputs()
        try:
            current_id = self.preset.id
            for preset in Preset.select().order_by(Preset.number):
                self.load_preset(preset.id, preload=True)
            self.load_preset(current_id)
            self.presets_preloaded = True
        finally:
            mgcore.resume_outputs()

    def unpreload_presets(self):
        signals.emit('clear:preload')
        self.presets_preloaded = False

    # FIXME: database access should not happen in this class!
    def load_preset(self, preset_id, preload=False):
        try:
            preset = Preset.get(Preset.id == int(preset_id))
        except Preset.DoesNotExist:
            log.error('Preset {} not found!'.format(preset_id))
            return
        with self.lock():
            with signals.suppress():
                self.from_preset_dict(preset.get_data())
                self.preset.id = preset_id
            if preload:
                signals.emit('active:preset:preload')
            signals.emit('active:preset:changed')
            self.last_preset_number = preset.number

    # FIXME: database access should not happen in this class!
    def save_preset(self, name=None, preset_id=None):
        if preset_id is not None:
            try:
                preset = Preset.get(Preset.id == int(preset_id))
            except Preset.DoesNotExist:
                log.error('Preset {} not found!'.format(preset_id))
                return
            if name is not None:
                preset.name = name
        else:
            preset = Preset()
            preset.name = name or 'Unnamed'

        preset.set_data(self.to_preset_dict())
        preset.save()
        signals.emit('preset:changed', {'id': preset.id})

    def clear(self):
        """
        Set the state to default values
        """
        self.last_preset_number = 0
        self.main_volume = 120
        self.reverb_volume = 25
        self.reverb_panning = 64
        self.coarse_tune = 0
        self.fine_tune = 0
        self.synth.clear()
        self.preset.clear()

    def to_preset_dict(self):
        return {
            'main': {
                'volume': self.main_volume,
                'gain': self.synth.gain,
                'pitchbend_range': self.pitchbend_range,
            },
            'tuning': {
                'coarse': self.coarse_tune,
                'fine': self.fine_tune,
            },
            'voices': self.preset.to_voices_dict(),
            'keynoise': {
                'soundfont': self.preset.keynoise[0].soundfont_id,
                'bank': self.preset.keynoise[0].bank,
                'program': self.preset.keynoise[0].program,
                'volume': self.preset.keynoise[0].volume,
                'panning': self.preset.keynoise[0].panning,
            },
            'reverb': {
                'volume': self.reverb_volume,
                'panning': self.reverb_panning,
            },
        }

    def from_preset_dict(self, data, partial=False):
        main = data.get('main', {})
        _set(self, 'main_volume', main, 'volume', 120, partial)
        _set(self.synth, 'gain', main, 'gain', 50, partial)
        _set(self, 'pitchbend_range', main, 'pitchbend_range', 100, partial)

        tuning = data.get('tuning', {})
        _set(self, 'coarse_tune', tuning, 'coarse', 0, partial)
        _set(self, 'fine_tune', tuning, 'fine', 0, partial)

        # FIXME: support for legacy chien threshold - remove in 1.5
        try:
            old_chien_style = data['voices']['trompette'][0]['chien_threshold'] and False
        except (KeyError, IndexError):
            old_chien_style = True

        if old_chien_style:
            chien_threshold = data.get('chien', {}).get('chien_threshold', None)
            if chien_threshold is not None:
                for i in (0, 1, 2):
                    try:
                        data['voices']['trompette'][i]['chien_threshold'] = chien_threshold
                    except (KeyError, IndexError):
                        pass

        self.preset.from_voices_dict(data.get('voices', {}), partial)

        self.preset.keynoise[0].from_dict(data.get('keynoise', {}), partial)

        reverb = data.get('reverb', {})
        _set(self, 'reverb_volume', reverb, 'volume', 25, partial)
        _set(self, 'reverb_panning', reverb, 'panning', 64, partial)

    def to_misc_dict(self):
        return {
            'ui': {
                'timeout': self.ui.timeout,
                'brightness': self.ui.brightness,
                'chien_sens_reverse': self.chien_sens_reverse,
                'multi_chien_threshold': self.multi_chien_threshold,
                'mod1_key_mode': self.mod1_key_mode,
                'mod2_key_mode': self.mod2_key_mode,
                'wrap_groups': self.wrap_groups,
                'wrap_presets': self.wrap_presets,
                'string_group_by_type': self.ui.string_group_by_type,
            },
            'keyboard': {
                'key_on_debounce': self.key_on_debounce,
                'key_off_debounce': self.key_off_debounce,
                'base_note_delay': self.base_note_delay,
            },
            'features': {
                'poly_base_note': self.poly_base_note,
                'poly_pitch_bend': self.poly_pitch_bend,
                'string_count': self.string_count,
            },
            'instrument_mode': self.instrument_mode,
        }

    def from_misc_dict(self, data, partial=False):
        features = data.get('features', {})
        ui = data.get('ui', {})
        keyboard = data.get('keyboard', {})

        _set(self, 'poly_base_note', features, 'poly_base_note', True, partial)
        _set(self, 'poly_pitch_bend', features, 'poly_pitch_bend', True, partial)

        _set(self.ui, 'timeout', ui, 'timeout', 10, partial)
        _set(self.ui, 'brightness', ui, 'brightness', 80, partial)
        _set(self, 'chien_sens_reverse', ui, 'chien_sens_reverse', False, partial)

        _set(self, 'key_on_debounce', keyboard, 'key_on_debounce', 2, partial)
        _set(self, 'key_off_debounce', keyboard, 'key_off_debounce', 10, partial)
        _set(self, 'base_note_delay', keyboard, 'base_note_delay', 20, partial)

        _set(self, 'instrument_mode', data, 'instrument_mode', 'simple_three', partial)

        if not self.set_instrument_mode(self.instrument_mode):
            _set(self, 'string_count', features, 'string_count', 1, partial)
            _set(self, 'mod1_key_mode', ui, 'mod1_key_mode', 'preset_prev', partial)
            _set(self, 'mod2_key_mode', ui, 'mod2_key_mode', 'preset_next', partial)
            _set(self, 'wrap_presets', ui, 'wrap_presets', False, partial)
            _set(self, 'wrap_groups', ui, 'wrap_groups', False, partial)
            _set(self.ui, 'string_group_by_type', ui, 'string_group_by_type', False, partial)
            self.ui.string_group = self.default_string_group()

        if self.string_count > 1:
            _set(self, 'multi_chien_threshold', ui, 'multi_chien_threshold', False, partial)
        else:
            self.multi_chien_threshold = False

    def set_instrument_mode(self, name):
        self.instrument_mode = name
        mode = INSTRUMENT_MODES.get(name)
        if not mode:
            return False
        self.string_count = mode['string_count']
        self.mod1_key_mode = mode['mod1_key_mode']
        self.mod2_key_mode = mode['mod2_key_mode']
        self.wrap_presets = mode['wrap_presets']
        self.wrap_groups = mode['wrap_groups']
        self.ui.string_group_by_type = mode['string_group_by_type']
        self.ui.string_group = self.default_string_group()

        return True

    def voice_is_active(self, voice):
        if self.ui.string_group_by_type:
            stype = STRING_TYPES[self.ui.string_group]
            return stype['name'] == voice.type
        else:
            return self.ui.string_group + 1 == voice.number

    def modify_string_group(self, mod_level, active, force=False):
        if self.ui.string_group_by_type:
            stype = STRING_TYPES[mod_level]
            group = stype['group']
        else:
            group = mod_level

        if force:
            self.ui.string_group = group
            self._mod_levels = []
            return

        if active:
            if group not in self._mod_levels:
                self._mod_levels.append(group)
            self.ui.string_group = group
        else:
            try:
                self._mod_levels.remove(group)
                group = self._mod_levels[-1]
            except (ValueError, IndexError):
                group = self.default_string_group()
            self.ui.string_group = group

    def inc_string_group(self, val, wrap=False):
        if self.ui.string_group_by_type:
            group_count = 3
        else:
            group_count = self.string_count

        group = self.ui.string_group + val

        if wrap:
            group = group % group_count
        else:
            group = max(0, min(group_count - 1, group))

        self.ui.string_group = group

    def default_string_group(self):
        if self.ui.string_group_by_type:
            return 1
        else:
            return 0

    def active_voice_list(self, string_group=None, string_group_by_type=None):
        if string_group is None:
            string_group = self.ui.string_group

        if string_group_by_type is None:
            string_group_by_type = self.ui.string_group_by_type

        if string_group_by_type:
            stype = STRING_TYPES[string_group]
            voices = getattr(self.preset, stype['name'])
            return voices[:self.string_count]
        else:
            return (self.preset.drone[string_group],
                    self.preset.melody[string_group],
                    self.preset.trompette[string_group])

    def toggle_voice_mute(self, idx, whole_group=False):
        """
        Toggle the voice muted state for a particular voice type. If
        whole_group is set, it toggles all voices in that group, otherwise
        only the voice of the currently active voice group.
        """
        if whole_group:
            voices = self.active_voice_list(idx, not self.ui.string_group_by_type)
            muted = all(v.muted for v in voices)
            for v in voices:
                v.muted = not muted
        else:
            voices = self.active_voice_list()
            try:
                voices[idx].muted = not voices[idx].muted
            except IndexError:
                pass  # happens if string count is set to a lower number


class UIState(EventEmitter):
    def __init__(self):
        super().__init__(prefix='ui')
        self.string_group = 0
        self.string_group_by_type = False
        self.brightness = 100
        self.timeout = 10

    def to_dict(self):
        return {
            'brightness': self.brightness,
            'timeout': self.timeout,
        }

    def from_dict(self, data, partial=False):
        _set(self, 'brightness', data, 'brightness', 80, partial)
        _set(self, 'timeout', data, 'timeout', 10, partial)


class PowerState(EventEmitter):
    def __init__(self, ac_state_file, usb_state_file, battery_voltage_file):
        super().__init__(prefix='power')
        self._log = logging.getLogger('system.power')

        self._ac_state_file = ac_state_file
        self._usb_state_file = usb_state_file
        self._battery_voltage_file = battery_voltage_file

        self.source = 'ext'
        self.battery_voltage = 0.0
        self.battery_percent = 0
        self.battery_max_voltage = 12  # FIXME: make this configurable for different battery chemistries
        self.battery_min_voltage = 7.5
        self.start_update()

    def get_power_source(self):
        try:
            with open(self._ac_state_file, 'r') as f:
                if f.read().strip() == '1':
                    return 'ext'
            with open(self._usb_state_file, 'r') as f:
                if f.read().strip() == '1':
                    return 'usb'
            return 'bat'
        except Exception:
            self._log.exception('Unable to get power source')
            return 'bat'

    def get_battery_voltage(self):
        try:
            with open(self._battery_voltage_file, 'r') as f:
                return int(f.read().strip()) / 1000
        except Exception:
            self._log.exception('Unable to get battery voltage')
            return 0

    def update_state(self):
        self.source = self.get_power_source()
        self.battery_voltage = self.get_battery_voltage()
        self.battery_percent = max(min(round(
            (self.battery_voltage - self.battery_min_voltage) / (
                self.battery_max_voltage - self.battery_min_voltage) * 100), 100), 0)

    def start_update(self):
        self._timer = PeriodicTimer(3, self.update_state)
        self._timer.start()


class SynthState(EventEmitter):
    def __init__(self):
        super().__init__(prefix='synth')
        self.gain = 50

    def clear(self):
        self.gain = 50

    def to_dict(self):
        return {
            'gain': self.gain,
        }

    def from_dict(self, data, partial=False):
        _set(self, 'gain', data, 'gain', 50, partial)


class VoiceState(EventEmitter):
    def __init__(self, type, prefix=None):
        super().__init__(prefix=prefix)
        with signals.suppress():
            self.type = type
            self.clear()

    def clear(self):
        self.soundfont_id = None
        self.bank = 0
        self.program = 0
        self.muted = True
        self.volume = 100
        self.panning = 64
        self.base_note = 60
        self.capo = 0
        self.polyphonic = False
        self.mode = 'midigurdy'
        self.finetune = 0
        self.chien_threshold = 50

    def to_dict(self):
        return {
            'soundfont': self.soundfont_id,
            'bank': self.bank,
            'program': self.program,
            'volume': self.volume,
            'panning': self.panning,
            'muted': self.muted,
            'note': self.base_note,
            'mode': self.mode,
            'capo': self.capo,
            'polyphonic': self.polyphonic,
            'finetune': self.finetune,
            'chien_threshold': self.chien_threshold,
        }

    def from_dict(self, data, partial=False):
        if 'soundfont' in data and 'bank' in data and 'program' in data:
            sf = SoundFont.by_id(data['soundfont']) if data['soundfont'] else None
            sound = sf.get_sound(data['bank'], data['program']) if sf else None
            if sound:
                self.set_sound(sound)
                if self.type == 'keynoise':
                    self.muted = False
                else:
                    _set(self, 'muted', data, 'muted', True, partial)
            else:
                self.clear_sound()
        elif not partial:
            self.clear_sound()

        _set(self, 'volume', data, 'volume', 100, partial)
        _set(self, 'panning', data, 'panning', 64, partial)
        _set(self, 'base_note', data, 'note', 60, partial)
        _set(self, 'capo', data, 'capo', 0, partial)
        _set(self, 'polyphonic', data, 'polyphonic', False, partial)
        _set(self, 'mode', data, 'mode', 'midigurdy', partial)
        _set(self, 'finetune', data, 'finetune', 0, partial)
        _set(self, 'chien_threshold', data, 'chien_threshold', 50, partial)

    def set_sound(self, sound):
        with signals.suppress():
            self.soundfont_id = sound.soundfont.id
            self.bank = sound.bank
            self.program = sound.program
        self.notify('sound:changed')
        if sound.base_note > -1:
            self.base_note = sound.base_note

        # reset the mode back to MidiGurdy when selecting a MidiGurdy specific sound
        if sound.soundfont.mode == 'midigurdy':
            self.mode = 'midigurdy'

    def clear_sound(self):
        do_update = False
        with signals.suppress() as events:
            self.soundfont_id = None
            self.bank = 0
            self.program = 0
            self.base_note = 60
            self.muted = True
            if events:
                do_update = True
        if do_update:
            self.notify('sound:changed')

    def get_sound(self):
        from mg.sf2 import SoundFont
        if self.soundfont_id:
            sf = SoundFont.by_id(self.soundfont_id)
            if sf:
                return sf.get_sound(self.bank, self.program)

    def is_silent(self):
        return self.muted or not self.soundfont_id or self.base_note < 0

    def has_midigurdy_soundfont(self):
        from mg.sf2 import SoundFont
        if not self.soundfont_id:
            return True
        sf = SoundFont.by_id(self.soundfont_id)
        if not sf:
            return True
        return sf.mode == 'midigurdy'

    def get_mode(self):
        if self.has_midigurdy_soundfont():
            return 'midigurdy'
        if self.mode == 'keyboard':
            return 'keyboard'
        return 'generic'


class MIDIPortState(EventEmitter):
    def __init__(self, port):
        super().__init__(prefix='midi:port')
        with signals.suppress():
            self.port = port
            self.input_enabled = False
            self.input_auto = False
            self.output_enabled = False
            self.output_auto = False

            # channels are 0-based, -1 means OFF
            self.melody_channel = 0
            self.trompette_channel = 1
            self.drone_channel = 2

            self.program_change = False
            self.speed = 0

    def to_midi_dict(self):
        return {
            'input_enabled': self.input_enabled,
            'input_auto': self.input_auto,
            'output_enabled': self.output_enabled,
            'output_auto': self.output_auto,
            'melody_channel': self.melody_channel,
            'drone_channel': self.drone_channel,
            'trompette_channel': self.trompette_channel,
            'program_change': self.program_change,
            'speed': self.speed,
        }

    def from_midi_dict(self, data, partial=False):
        _set(self, 'melody_channel', data, 'melody_channel', 0, partial)
        _set(self, 'trompette_channel', data, 'trompette_channel', 1, partial)
        _set(self, 'drone_channel', data, 'drone_channel', 2, partial)
        _set(self, 'program_change', data, 'program_change', False, partial)
        _set(self, 'speed', data, 'speed', 0, partial)

        _set(self, 'input_auto', data, 'input_auto', False, partial)
        if self.input_auto:
            _set(self, 'input_enabled', data, 'input_enabled', False, partial)

        _set(self, 'output_auto', data, 'output_auto', False, partial)
        if self.output_auto:
            _set(self, 'output_enabled', data, 'output_enabled', False, partial)


class MIDIState(EventEmitter):
    def __init__(self):
        super().__init__(prefix='midi')
        with signals.suppress():
            self.port_states = None
            self.udc_config = -1

    def get_port_states(self):
        if self.port_states is None:
            with signals.suppress():
                self.port_states = {}
                self.update_port_states()
        return sorted(self.port_states.values(), key=lambda s: s.port.id)

    def update_port_states(self):
        if self.port_states is None:
            self.port_states = {}

        rawmidi_ports = []
        for p in RawMIDI().get_ports():
            # which internal MIDI port to use depends on the currently
            # selected UDC (USB gadget) configuration.
            if p.id.startswith('f_midi') and p.card_idx != self.udc_config:
                continue
            rawmidi_ports.append(p)

        ports = {p.id: p for p in rawmidi_ports}
        to_add = [pid for pid in ports if pid not in self.port_states]
        to_remove = [pid for pid in self.port_states if pid not in ports]

        for pid in to_remove:
            port_state = self.port_states.pop(pid, None)
            signals.emit('midi:port:removed', {'port_state': port_state})

        for pid in to_add:
            port = ports[pid]
            port_state = MIDIPortState(port)
            self.port_states[pid] = port_state
            signals.emit('midi:port:added', {'port_state': port_state})

            config = load_midi_config(port.id)
            if config:
                port_state.from_midi_dict(config)

        if to_add or to_remove:
            signals.emit('midi:changed')


class PresetState(EventEmitter):
    def __init__(self, prefix=None):
        super().__init__(prefix=prefix)
        self.id = 0
        self.name = 'Unnamed'
        self.number = 0
        self.voices = []
        with signals.suppress():
            self.melody = self._voice_state(3, 0, 'melody')
            self.drone = self._voice_state(3, 3, 'drone')
            self.trompette = self._voice_state(3, 6, 'trompette')
            self.keynoise = self._voice_state(1, 9, 'keynoise')

    def clear(self):
        for voice_type in ('melody', 'drone', 'trompette', 'keynoise'):
            for voice in getattr(self, voice_type):
                voice.clear()
        self.keynoise[0].volume = 20

    def to_voices_dict(self):
        return {
            'melody': [v.to_dict() for v in self.melody],
            'drone': [v.to_dict() for v in self.drone],
            'trompette': [v.to_dict() for v in self.trompette],
        }

    def from_voices_dict(self, data, partial=False):
        for voice_type in ('melody', 'drone', 'trompette', 'keynoise'):
            voices = getattr(self, voice_type)
            voice_data = data.get(voice_type, [])
            for voice_idx in range(len(voices)):
                if voice_idx < len(voice_data):
                    voices[voice_idx].from_dict(voice_data[voice_idx])
                elif not partial:
                    voices[voice_idx].clear()

    def _voice_state(self, num, start_channel, vtype):
        voices = []
        for i in range(num):
            voice = VoiceState(vtype, prefix='{}:voice'.format(self.prefix))
            voice.channel = start_channel + i
            voice.number = i + 1
            voice.string = '%s%d' % (voice.type, voice.number)
            voices.append(voice)
            self.voices.append(voice)
        return voices

    def voice_by_number(self, number):
        try:
            return self.voices[number]
        except IndexError:
            log.error('Invalid string number: {}'.format(number))

    def voices_by_type(self, stype):
        if stype in ('melody', 'drone', 'trompette', 'keynoise'):
            return getattr(self, stype)
        raise RuntimeError(f'Invalid string type "{stype}"')

    def set_chien_thresholds(self, thresholds):
        num = len(thresholds or [])
        for i in (0, 1, 2):
            if num > i and thresholds[i] is not None:
                self.trompette[i].chien_threshold = thresholds[i]

    def get_chien_thresholds(self):
        return [
            self.trompette[0].chien_threshold,
            self.trompette[1].chien_threshold,
            self.trompette[2].chien_threshold,
        ]


def _set(state, attr, data, name, default=None, partial=False):
    if name in data:
        if getattr(state, attr) != data[name]:
            setattr(state, attr, data[name])
            return True
    elif not partial:
        if getattr(state, attr) != default:
            setattr(state, attr, default)
            return True
