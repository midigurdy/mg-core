import time
from .base import Page, Slider, Deck

from mg.input import Action, Key
from mg.utils import midi2percent, midi2note


class Home(Page):
    state_events = [
        'active:preset:changed',
        'last_preset_number:changed',
        'active:preset:voice:muted:changed',
        'active:preset:voice:base_note:changed',
        'active:preset:voice:sound:changed',
        'ui:string_group:changed',
        'power:source:changed',
        'power:battery_percent:changed',
    ]

    def handle_state_event(self, name, data):
        if name == 'power:battery_percent:changed' and self.state.power.source != 'bat':
            return
        if name == 'ui:string_group:changed' and self.state.ui.string_group > 0:
            self.render(self.state.ui.string_group)
            time.sleep(0.10)
        self.render()

    def timeout(self):
        self.render()

    def render(self, hide_group=-1):
        with self.menu.display as d:
            labels = (
                (3, 'Drone'),
                (33, 'Melody'),
                (68, 'Tromp'),
                (100, 'Preset'),
            )
            strings = (
                (2, 0, self.state.preset.drone),
                (34, 0, self.state.preset.melody),
                (66, 0, self.state.preset.trompette)
            )
            for x, y, st in strings:
                self.draw_string_box(d, x, y, st, hide_group)

            d.font_size(1)
            for x, label in labels:
                d.puts(x, 24, label)

            d.puts(114, 14, '{}'.format(self.state.last_preset_number or '-'),
                   align='center', anchor='center')

            d.puts(113, 0, self.state.power.source.upper(), align='right', anchor='right')
            self.render_battery_icon(d)

    def render_battery_icon(self, d):
        bx = 116
        d.rect(bx, 1, bx + 1, 4)  # bat pole
        d.rect(bx + 1, 0, bx + 11, 5)  # bat body outline
        width = round(self.state.power.battery_percent / 100 * 9)
        if width > 0:
            # charge indication
            d.rect(bx + 2 + (9 - width), 1, bx + 11, 4, fill=1)
        else:
            # diagonal line
            d.line(bx + 1, 5, bx + 11, 0)

    def draw_string_box(self, d, x, y, string, hide_group=-1):
        w = 26
        c = 14
        h1 = 12
        h2 = 9
        d.font_size(3)

        d.rect(x, y, x + w, y + 12,
               color=0,
               fill=0 if string[0].is_silent() else 1)

        if hide_group != 0:
            if string[0].soundfont_id is not None:
                note = midi2note(string[0].base_note, False)
            else:
                note = '-'
            d.puts(x + c, y + 2, note,
                   anchor='center', align='center',
                   color=1 if string[0].is_silent() else 0)

        d.font_size(1)

        d.rect(x, y + h1, x + 13, y + h1 + h2,
               color=0,
               fill=0 if string[1].is_silent() else 1)

        if hide_group != 1:
            if string[1].soundfont_id is not None:
                note = midi2note(string[1].base_note, False)
            else:
                note = '-'
            d.puts(x + 7, y + h1 + 2, note,
                   anchor='center', align='center',
                   color=1 if string[1].is_silent() else 0)

        d.rect(x + 13, y + h1, x + w, y + h1 + h2,
               color=0,
               fill=0 if string[2].is_silent() else 1)

        if hide_group != 2:
            if string[2].soundfont_id is not None:
                note = midi2note(string[2].base_note, False)
            else:
                note = '-'
            d.puts(x + w - 6, y + h1 + 2, note,
                   anchor='center', align='center',
                   color=1 if string[2].is_silent() else 0)

        d.rect(x, y, x + w, y + h1 + h2,
               color=1)

        d.point(x, y, 0)
        d.point(x + w, y, 0)
        d.point(x, y + h1 + h2, 0)
        d.point(x + w, y + h1 + h2, 0)
        d.point(x, y + h1, 0)
        d.point(x + w, y + h1, 0)
        d.point(x + 13, y + h1 + h2, 0)


class ChienThresholdPage(Slider):
    title = 'Chien Sens'
    render_on_input = False
    state_events = ['chien_threshold:changed']
    minval = 0
    maxval = 100
    idle_timeout = 5

    def handle_state_event(self, name, data):
        self.render()

    def get_value(self):
        self.threshold = self.state.chien_threshold
        return self.threshold

    def set_value(self, val):
        self.threshold = val
        with self.state.lock():
            self.state.chien_threshold = self.threshold


class VolumeSlider(Slider):
    minval = 0
    maxval = 127
    render_on_input = False

    def __init__(self, param, title):
        self.title = title
        self.param = param
        self.state_events = ['%s:changed' % param]

    def get_value_percent(self):
        return midi2percent(self.get_value())

    def handle_state_event(self, name, data):
        self.render()

    def get_value(self):
        self.value = getattr(self.state, self.param)
        return self.value

    def set_value(self, val):
        # remove equal percent steps due to rounding errors
        if self.value != val and midi2percent(self.value) == midi2percent(val):
            val += 1 if self.value < val else -1
        setattr(self.state, self.param, val)
        self.value = val


class KeynoiseVolumeSlider(VolumeSlider):
    minval = 0
    maxval = 127
    render_on_input = False
    state_events = ['active:preset:voice:volume:changed']

    def __init__(self, title):
        self.title = title

    def get_value_percent(self):
        return midi2percent(self.get_value())

    def handle_state_event(self, name, data):
        self.render()

    def get_value(self):
        self.value = self.state.preset.keynoise[0].volume
        return self.value

    def set_value(self, val):
        # remove equal percent steps due to rounding errors
        if self.value != val and midi2percent(self.value) == midi2percent(val):
            val += 1 if self.value < val else -1
        self.state.preset.keynoise[0].volume = val
        self.value = val


class VolumeDeck(Deck):
    idle_timeout = 5
    pages = [
        VolumeSlider('main_volume', 'Main Volume'),
        VolumeSlider('reverb_volume', 'Reverb Volume'),
        KeynoiseVolumeSlider('Key Volume'),
    ]


class MessagePage(Page):
    def __init__(self, message, modal=False, font_size=3, timeout=None):
        self.message = message
        self.font_size = font_size
        self.modal = modal
        self.idle_timeout = timeout

    def render(self):
        num_lines = self.message.count('\n') + 1
        with self.menu.display as d:
            d.font_size(self.font_size)
            cy = int(16 - ((d.font.char_height / 2) * num_lines))
            d.puts(64, cy, self.message, align='center', anchor='center')

    def handle(self, ev):
        if not self.modal and ev.down():
            self.menu.pop()
        return True


class PoweroffPage(MessagePage):
    def __init__(self):
        super().__init__('Hold 2 seconds\nto power off', modal=True)

    def handle(self, ev):
        if ev.name == Key.fn4 and ev.action == Action.up:
            self.menu.pop()
        return True
