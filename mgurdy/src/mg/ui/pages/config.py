from .base import ConfigList, ValueListItem, Page, BooleanListItem
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


class MIDIConnectionState(ValueListItem):
    minval = 0
    maxval = 2
    zero_value = 0

    def __init__(self, port_state, enabled_attr, auto_attr, label):
        self.port_state = port_state
        self.enabled_attr = enabled_attr
        self.auto_attr = auto_attr
        self.label = label
        super().__init__()

    def set_value(self, val):
        self.value = val
        setattr(self.port_state, self.enabled_attr, val > 0)
        setattr(self.port_state, self.auto_attr, val == 2)

    def get_value(self):
        enabled = getattr(self.port_state, self.enabled_attr, False)
        auto = getattr(self.port_state, self.auto_attr, False)
        if enabled and auto:
            value = 2
        elif enabled:
            value = 1
        else:
            value = 0
        self.value = value
        return self.value

    def format_value(self, val):
        if val == 2:
            return 'Auto-On'
        elif val:
            return 'On'
        else:
            return 'Off'


class MIDIConnectionSpeed(ValueListItem):
    label = 'Speed'
    minval = 0
    maxval = 2
    zero_val = 0

    def __init__(self, port_state):
        self.port_state = port_state
        super().__init__()

    def set_value(self, val):
        self.value = val
        setattr(self.port_state, 'speed', val)

    def get_value(self):
        self.value = getattr(self.port_state, 'speed', 0)
        return self.value

    def format_value(self, val):
        if val == 0:
            return 'Normal'
        elif val == 1:
            return 'Fast'
        elif val > 1:
            return 'Unlimited'


class MIDIChannelItem(ValueListItem):
    minval = -1
    maxval = 15

    def __init__(self, port_state, attr, label, default_channel):
        self.zero_value = default_channel
        self.port_state = port_state
        self.attr = attr
        self.label = label
        super().__init__()

    def set_value(self, val):
        setattr(self.port_state, self.attr, val)
        self.value = val

    def get_value(self):
        self.value = getattr(self.port_state, self.attr, self.zero_value)
        return self.value

    def format_value(self, val):
        return '{}'.format(val + 1 if val >= 0 else 'Off')


class MIDIOutputConfig(ConfigList):
    def __init__(self, port_state):
        self.port_state = port_state
        super().__init__()

    def get_items(self):
        return [
            MIDIChannelItem(self.port_state, 'melody_channel', 'Melody Channel', 1),
            MIDIChannelItem(self.port_state, 'trompette_channel', 'Tromp. Channel', 2),
            MIDIChannelItem(self.port_state, 'drone_channel', 'Drone Channel', 3),
            BooleanListItem(self.port_state, 'program_change', 'Program Change'),
            MIDIConnectionSpeed(self.port_state),
        ]


class MIDIPortPage(ConfigList):
    state_events = [
        'midi:port:removed',
    ]

    def __init__(self, port_state, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port_state = port_state
        self._prev_state = {}

    def show(self, *args, **kwargs):
        self._prev_state = self.port_state.to_midi_dict()
        super().show(*args, **kwargs)

    def hide(self):
        curr_state = self.port_state.to_midi_dict()
        if self._prev_state != curr_state:
            db.save_midi_config(self.port_state.port.id, curr_state)
        super().hide()

    def handle_state_event(self, name, data):
        # if this port got removed, show notice and return to home
        if data.get('port_state', None) == self.port_state:
            self.menu.message('MIDI Port removed', 2)
            return True

    def get_items(self):
        return [
            MIDIConnectionState(self.port_state, 'input_enabled', 'input_auto', 'Input'),
            MIDIConnectionState(self.port_state, 'output_enabled', 'output_auto', 'Output'),
            PopupItem('Output Setup' + chr(127), MIDIOutputConfig(self.port_state)),
        ]


class NoMIDIDevices(Spacer):
    label = '- No MIDI devices -'

    def show_cursor(self):
        return False


class MIDIPortPopupItem(PopupItem):
    def __init__(self, port_state):
        self.port_state = port_state
        self.page = MIDIPortPage(port_state)
        name = port_state.port.name
        if name == 'f_midi':  # this is the USB MIDI Gadget
            name = 'Main MIDI'
        self.label = name[0:15] + chr(127)

    def get_value_display(self):
        return '|{}{}'.format(
            'I' if self.port_state.input_enabled else ' ',
            'O' if self.port_state.output_enabled else ' '
        )

    def render_on(self, display, x, y, width):
        display.puts(x, y, self.get_label())

        right = x + width

        icon = {
            'io': chr(34),
            'iO': chr(35),
            'Io': chr(36),
            'IO': chr(37),
        }['{}{}'.format(
            'I' if self.port_state.input_enabled else 'i',
            'O' if self.port_state.output_enabled else 'o',
        )]
        display.font_size(9)
        display.puts(right, y, icon, align='right', anchor='right')
        display.font_size(3)


class MIDIPage(ConfigList):
    state_events = [
        'midi:changed',
    ]

    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    def handle_state_event(self, name, data):
        for item in self.visible_items:
            item.hide()
        self.visible_items = []
        self.deactivate_active_item()
        self.set_pos(0)
        self.set_items(self.get_items())
        for item in self.items:
            item.init(self.menu, self.state)
        self.render()

    def timeout(self):
        self.menu.goto('home')

    def get_items(self):
        items = [MIDIPortPopupItem(ps) for ps in self.state.midi.get_port_states()]
        if items:
            return items
        else:
            return [NoMIDIDevices()]


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
            PopupItem('Keynoise' + chr(127), KeynoisePage(
                'Keynoise',
                voice_name='preset.keynoise.0',
                sync_state=False)),
            PopupItem('MIDI' + chr(127), MIDIPage()),
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
