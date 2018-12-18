from .base import ConfigList, ValueListItem, Page
from .presets import PresetsPage

from mg.input import Key
from mg.utils import midi2percent
from mg import db

from .base import PopupItem
from .strings import KeynoisePage


class CoarseTuneItem(ValueListItem):
    label = 'Coarse Tune'
    zero_value = 0
    minval = -63
    maxval = 64

    def format_value(self, val):
        return '{}{}'.format('+' if val > 0 else '', val)

    def set_value(self, val):
        self.state.coarse_tune = val

    def get_value(self):
        return self.state.coarse_tune


class FineTuneItem(ValueListItem):
    label = 'Fine Tune'
    zero_value = 0
    minval = -100
    maxval = 100

    def format_value(self, val):
        return '{}{} Ct'.format('+' if val > 0 else '', val)

    def set_value(self, val):
        self.state.fine_tune = val

    def get_value(self):
        return self.state.fine_tune


class PitchbendRangeItem(ValueListItem):
    label = 'Pitch Bend'
    zero_value = 0
    minval = 0
    maxval = 200

    def format_value(self, val):
        return '{} Ct'.format(val)

    def set_value(self, val):
        self.state.pitchbend_range = val

    def get_value(self):
        return self.state.pitchbend_range


class MiscConfigItem(ValueListItem):
    def __init__(self):
        super().__init__()
        self.dirty = False

    def activate(self, parent):
        self.dirty = False
        self.active = True

    def deactivate(self):
        if self.dirty:
            db.save_misc_config(self.state.to_misc_dict())
            self.dirty = False
        self.active = False


class BrightnessItem(MiscConfigItem):
    label = 'Brightness'

    def get_value(self):
        return self.state.ui.brightness

    def set_value(self, val):
        if self.state.ui.brightness != val:
            self.state.ui.brightness = val
            self.dirty = True


class DisplayTimeoutItem(MiscConfigItem):
    label = 'Disp. Timeout'
    minval = 0
    maxval = 60

    def get_value(self):
        return self.state.ui.timeout

    def set_value(self, val):
        if self.state.ui.timeout != val:
            self.state.ui.timeout = val
            self.dirty = True

    def format_value(self, val):
        if val:
            return '{}s'.format(val)
        else:
            return 'off'


class SynthGainItem(ValueListItem):
    label = 'Synth Gain'
    maxval = 127

    def set_value(self, val):
        # remove equal percent steps due to rounding errors
        if self.value != val and midi2percent(self.value) == midi2percent(val):
            val += 1 if self.value < val else -1
        self.state.synth.gain = val
        self.value = val

    def get_value(self):
        self.value = self.state.synth.gain
        return self.value

    def format_value(self, val):
        return '{:3d}%'.format(midi2percent(val))


class Spacer(ValueListItem):
    label = '--------------------'

    def activate(self, *args, **kwargs):
        pass

    def deactivate(self):
        pass

    def get_value(self):
        return ''

    def get_value_display(self):
        return ''


class MIDIPortItem(ValueListItem):
    minval = 0
    maxval = 1

    def __init__(self, port):
        super().__init__()
        self.port = port

    @property
    def label(self):
        return self.port.name

    def set_value(self, val):
        with self.state.lock():
            self.port.enabled = bool(val)

    def get_value(self):
        return int(self.port.enabled)

    def format_value(self, value):
        return 'On' if value else 'Off'


class MIDIPage(ConfigList):
    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    def timeout(self):
        self.menu.goto('home')

    def get_items(self):
        return [MIDIPortItem(port) for port in self.state.midi.ports]


class ConfigPage(ConfigList):
    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    def timeout(self):
        self.menu.goto('home')

    def get_items(self):
        return [
            CoarseTuneItem(),
            FineTuneItem(),
            PitchbendRangeItem(),
            SynthGainItem(),
            PopupItem('Keynoise...', KeynoisePage(
                'Keynoise',
                voice_name='preset.keynoise.0',
                sync_state=False)),
            PopupItem('MIDI...', MIDIPage()),
            Spacer(),
            BrightnessItem(),
            DisplayTimeoutItem(),
        ]


class PresetConfigDeck(Page):
    def __init__(self):
        self.next_idx = -1
        self.child = None

    def show(self, **kwargs):
        if self.next_idx == -1:
            self.show_next_page()

    def handle(self, ev):
        if ev.down(Key.fn4):
            self.show_next_page()
            return True
        if ev.pressed(Key.back):
            self.menu.pop(upto=self)
            return True

    def show_next_page(self):
        if self.child:
            self.menu.pop(upto=self.child)

        if self.next_idx <= 0:
            self.next_idx = 1
            self.child = PresetsPage()
            self.menu.push(self.child)
        else:
            self.next_idx = 0
            self.child = ConfigPage()
            self.menu.push(self.child)
