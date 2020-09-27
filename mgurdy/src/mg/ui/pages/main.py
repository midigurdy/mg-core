import time
from .base import Page, Slider, Deck

from mg.input import Action, Key
from mg.utils import midi2percent, midi2note
from mg.ui.display import blit


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
        'string_count:changed',
    ]

    def handle_state_event(self, name, data):
        if name == 'power:battery_percent:changed' and self.state.power.source != 'bat':
            return
        self.render()

    def timeout(self):
        self.render()  # FIXME: why is this needed? It depends on the display timeout!

    def render(self, hide_group=-1):
        with self.menu.display as d:
            for x, y, strings, label in (
                (0, 0, self.state.preset.drone, 'Drone'),
                (34, 0, self.state.preset.melody, 'Melody'),
                (67, 0, self.state.preset.trompette, 'Tromp'),
            ):
                if self.state.string_count == 1:
                    self.draw_string_boxes1(d, x, y, strings[0], label)
                elif self.state.string_count == 2:
                    self.draw_string_boxes2(d, x, y, strings[:2], label)
                elif self.state.string_count == 3:
                    self.draw_string_boxes3(d, x, y, strings, label)

            d.font_size(1)
            d.puts(100, 24, 'Preset')

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

    def _string_note(self, string):
        if string.soundfont_id is not None:
            return midi2note(string.base_note + self.state.coarse_tune, False)

    def draw_string_boxes1(self, d, x, y, string, label):
        d.font_size(1)
        d.puts(x + 13, 24, label, anchor='center', align='center')

        silent = string.is_silent()

        box = blit.SBOX_1[0 if silent else 1]
        d.blit(x + 1, y + 2, box.data, box.width)

        d.font_size(7)
        note = self._string_note(string)
        if note:
            d.puts(x + 13, y + 4, note, anchor='center', align='center', color=1 if silent else 0)

    def draw_string_boxes2(self, d, x, y, strings, label):
        d.font_size(1)
        d.puts(x + 14, 24, label, anchor='center', align='center')

        d.font_size(3)
        for i, string in enumerate(strings):
            silent = string.is_silent()
            active = i == self.state.ui.string_group

            widget = blit.SBOX_2_ACTIVE if active else blit.SBOX_2
            box = widget[0 if silent else 1]
            d.blit(x, y, box.data, box.width)

            note = self._string_note(string)
            if note:
                d.puts(x + 15, y + 1, note, anchor='center', align='center', color=1 if silent else 0)
            y += 12

    def draw_string_boxes3(self, d, x, y, strings, label):
        box = {
            'Drone': blit.SBOX_DRONE,
            'Melody': blit.SBOX_MELODY,
            'Tromp': blit.SBOX_TROMPETTE,
        }[label]

        d.blit(x, y + self.state.ui.string_group * 10, box.data, box.width)

        x += box.width
        d.font_size(3)

        for string in strings:
            silent = string.is_silent()

            note = self._string_note(string)
            box = blit.SBOX_3[0 if silent else 1]
            d.blit(x, y, box.data, box.width)

            if note:
                d.puts(x + 10, y + 1, note, anchor='center', align='center', color=1 if silent else 0)

            y += 10


class ChienThresholdPage(Slider):
    title = 'Chien Sens'
    render_on_input = True
    state_events = [
        'active:preset:voice:chien_threshold:changed',
    ]
    minval = 0
    maxval = 100
    idle_timeout = 5

    def __init__(self):
        super().__init__()
        self.thresholds = []

    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    @property
    def reverse_direction(self):
        return self.state.chien_sens_reverse

    def handle_state_event(self, name, data):
        # prevent rendering three times if all chiens have changed
        thresholds = self.state.preset.get_chien_thresholds()
        if self.thresholds != thresholds:
            self.render()

    def get_value(self):
        thresholds = self.state.preset.get_chien_thresholds()
        return thresholds[0]

    def set_value(self, val):
        self.thresholds = [val, val, val]
        with self.state.lock():
            self.state.preset.set_chien_thresholds(self.thresholds)


class MultiChienThresholdPage(Page):
    title = 'Chien Sensitivity'
    minval = 0
    maxval = 100
    state_events = [
        'active:preset:voice:chien_threshold:changed',
    ]

    def __init__(self):
        self.prevts = time.time()
        self.prevdir = 0
        self.chien_idx = 0
        self.thresholds = []

    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    @property
    def reverse_direction(self):
        return self.state.chien_sens_reverse

    def handle_state_event(self, name, data):
        # prevent rendering three times if all chiens have changed
        thresholds = self.state.preset.get_chien_thresholds()
        if self.thresholds != thresholds:
            self.render()

    def set_value(self, inc):
        self.thresholds = self.state.preset.get_chien_thresholds()
        for i in (0, 1, 2):
            if self.chien_idx == 0 or i == (self.chien_idx - 1):
                self.thresholds[i] = max(self.minval, min(self.maxval, self.thresholds[i] + inc))
        with self.state.lock():
            self.state.preset.set_chien_thresholds(self.thresholds)
        self.render()

    def show(self, **kwargs):
        self.prevts = time.time()
        self.prevdir = 0
        super().show(**kwargs)

    def handle(self, ev):
        if ev.name == Key.encoder:
            event_value = ev.value
            if self.reverse_direction:
                event_value *= -1
            inc = event_value
            if self.prevdir == inc:
                diff = ev.ts - self.prevts
                if diff < 30000:
                    inc *= 5
                elif diff < 50000:
                    inc *= 2
            self.prevts = ev.ts
            self.prevdir = event_value
            self.set_value(inc)
            return True
        elif ev.pressed(Key.select):
            self.chien_idx += 1
            self.chien_idx = self.chien_idx % 4
            self.render()
            return True

    def render(self):
        with self.menu.display as d:
            d.font_size(0)
            d.puts(64, 0, self.title, anchor='center')

            y = 7
            height = 5
            margin = 4

            # Output a slider for each trompette string
            for i in (0, 1, 2):
                val = self.state.preset.trompette[i].chien_threshold
                active = (i == (self.chien_idx - 1) or self.chien_idx == 0)

                if active:
                    # if chien is active, draw number inverted
                    # and output frame around slider
                    d.rect(0, y - 1, 5, y + 6, fill=1)
                    d.rect(8, y, 109, y + height)

                d.font_size(1)
                d.puts(1, y, '{}'.format(i + 1), color=0 if active else 1)

                if val > 0:
                    d.rect(9, y + 1, 8 + val, y + height - 1, fill=1)

                # 100% label needs a smaller font size to fit
                if val == 100:
                    d.font_size(0)
                    d.puts(127, y + 1, '{}%'.format(val), anchor='right')
                else:
                    d.font_size(1)
                    d.puts(127, y, '{}%'.format(val), anchor='right')

                y += height + margin


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
