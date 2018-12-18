from collections import OrderedDict
from contextlib import contextmanager
import threading
import logging

from mg.signals import EventEmitter, signals
from mg.utils import PeriodicTimer
from mg.db import Preset
from mg.sf2 import SoundFont


log = logging.getLogger('state')

AC_ONLINE_STATE = '/sys/class/power_supply/axp20x-ac/online'
USB_ONLINE_STATE = '/sys/class/power_supply/axp20x-usb/online'
BAT_VOLTAGE = '/sys/class/hwmon/hwmon0/in1_input'


class State(EventEmitter):
    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()
        self._obj_path_cache = {}

        with signals.suppress():
            self.preset = PresetState(prefix='active:preset')

            self.main_volume = 0
            self.reverb_volume = 0
            self.reverb_panning = 0
            self.coarse_tune = 0
            self.fine_tune = 0
            self.chien_threshold = 0
            self.last_preset_number = 0
            self.pitchbend_range = 0

            self.key_on_debounce = 2
            self.key_off_debounce = 10
            self.base_note_delay = 20
            self.chien_sens_reverse = False

            self.ui = UIState()
            self.synth = SynthState()
            self.power = PowerState()

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
            except:
                log.exception('Unable to resolve obj path "{}"'.format(path))
        return cached

    # FIXME: database access should not happen in this class!
    def load_preset(self, preset_id):
        try:
            preset = Preset.get(Preset.id == int(preset_id))
        except Preset.DoesNotExist:
            log.error('Preset {} not found!'.format(preset_id))
            return
        with self.lock():
            with signals.suppress():
                self.from_preset_dict(preset.get_data())
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
        self.chien_threshold = 50
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
            'chien': {
                'threshold': self.chien_threshold,
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

        chien = data.get('chien', {})
        _set(self, 'chien_threshold', chien, 'threshold', 50, partial)

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
            },
            'keyboard': {
                'key_on_debounce': self.key_on_debounce,
                'key_off_debounce': self.key_off_debounce,
                'base_note_delay': self.base_note_delay,
            }
        }

    def from_misc_dict(self, data, partial=False):
        ui = data.get('ui', {})
        _set(self.ui, 'timeout', ui, 'timeout', 10, partial)
        _set(self.ui, 'brightness', ui, 'brightness', 80, partial)
        _set(self, 'chien_sens_reverse', ui, 'chien_sens_reverse', False, partial)

        keyboard = data.get('keyboard', {})
        _set(self, 'key_on_debounce', keyboard, 'key_on_debounce', 2, partial)
        _set(self, 'key_off_debounce', keyboard, 'key_off_debounce', 10, partial)
        _set(self, 'base_note_delay', keyboard, 'base_note_delay', 20, partial)

    def toggle_voice_mute(self, vtype, whole_group=False):
        """
        Toggle the voice muted state for a particular voice type. If
        whole_group is set, it toggles all voices in that group, otherwise
        only the voice of the currently active voice group.
        """
        voice = getattr(self.preset, vtype)
        if whole_group:
            muted = all(v.muted for v in voice)
            for v in voice:
                v.muted = not muted
        else:
            group = self.ui.string_group
            voice[group].muted = not voice[group].muted


class UIState(EventEmitter):
    def __init__(self):
        super().__init__(prefix='ui')
        self.string_group = 0
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
    def __init__(self):
        super().__init__(prefix='power')
        self._log = logging.getLogger('system.power')
        self.source = 'ext'
        self.battery_voltage = 0.0
        self.battery_percent = 0
        self.battery_max_voltage = 12  # FIXME: make this configurable for different battery chemistries
        self.battery_min_voltage = 7.5
        self.start_update()

    def get_power_source(self):
        try:
            with open(AC_ONLINE_STATE, 'r') as f:
                if f.read().strip() == '1':
                    return 'ext'
            with open(USB_ONLINE_STATE, 'r') as f:
                if f.read().strip() == '1':
                    return 'usb'
            return 'bat'
        except:
            self._log.exception('Unable to get power source')
            return 'bat'

    def get_battery_voltage(self):
        try:
            with open(BAT_VOLTAGE, 'r') as f:
                return int(f.read().strip()) / 1000
        except:
            self._log.exception('Unable to get battery voltage')
            return 0

    def update_state(self):
        self.source = self.get_power_source()
        self.battery_voltage = self.get_battery_voltage()
        self.battery_percent = max(min(round(
            (self.battery_voltage - self.battery_min_voltage) /
            (self.battery_max_voltage - self.battery_min_voltage) *
            100), 100), 0)

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
        }

    def from_dict(self, data, partial=False):
        if 'soundfont' in data and 'bank' in data and 'program' in data:
            sf = SoundFont.by_id(data['soundfont'])
            sound = sf.get_sound(data['bank'], data['program']) if sf else None
            if sound:
                self.set_sound(sound)
            else:
                self.clear_sound()
        elif not partial:
            self.clear_sound()

        _set(self, 'muted', data, 'muted', True, partial)
        _set(self, 'volume', data, 'volume', 100, partial)
        _set(self, 'panning', data, 'panning', 64, partial)
        _set(self, 'base_note', data, 'note', 60, partial)
        _set(self, 'capo', data, 'capo', 0, partial)
        _set(self, 'polyphonic', data, 'polyphonic', False, partial)
        _set(self, 'mode', data, 'mode', 'midigurdy', partial)
        _set(self, 'finetune', data, 'finetune', 0, partial)

    def set_sound(self, sound):
        with signals.suppress():
            self.soundfont_id = sound.soundfont.id
            self.bank = sound.bank
            self.program = sound.program
        self.notify('sound:changed')
        if sound.base_note > -1:
            self.base_note = sound.base_note

    def clear_sound(self):
        with signals.suppress():
            self.soundfont_id = None
            self.bank = 0
            self.program = 0
            self.base_note = 60
            self.muted = True
        self.notify('sound:changed')

    def get_sound(self):
        from mg.sf2 import SoundFont
        if self.soundfont_id:
            sf = SoundFont.by_id(self.soundfont_id)
            if sf:
                return sf.get_sound(self.bank, self.program)

    def is_silent(self):
        return self.muted or not self.soundfont_id or self.base_note < 0


class MIDIPortState(EventEmitter):
    def __init__(self):
        super().__init__(name, device, direction, prefix='midi:port')
        with signals.suppress():
            self.name = 'Unnamed'
            self.device = None
            self.direction = None
            self.enabled = False


class MIDIState(EventEmitter):
    def __init__(self):
        super().__init__(prefix='midi')
        with signals.suppress():
            self.ports = OrderedDict()

    def get_ports(self):
        return list(self.ports.values())

    def add_port(self, name, device, direction):
        if device in self.ports:
            raise RuntimeError('Port for MIDI device {} already registered'.format(device))
        port = MIDIPortState(name, device, direction)
        self.ports[device] = port
        signals.emit('midi:port:added', {'port': port})

    def remove_port(self, device):
        port = self.ports.pop(device, None)
        if port:
            signals.emit('midi:port:removed', {'port': port})

    def get_port_by_device(self, device):
        for port in self.ports:
            if port.device == device:
                return port


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


def _set(state, attr, data, name, default=None, partial=False):
    if name in data:
        setattr(state, attr, data[name])
    elif not partial:
        setattr(state, attr, default)
