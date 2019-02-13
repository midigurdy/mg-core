import time
import math

from mg.input import Action, Key
from mg.signals import signals


class Page:
    title = ''
    idle_timeout = 0
    state_events = []

    def init(self, menu, state):
        self.state = state
        self.menu = menu

    def show(self, from_child=None, render=True):
        for name in self.state_events:
            signals.register(name, self.menu.enqueue_state_event)
        if render:
            self.render()

    def hide(self):
        for name in self.state_events:
            signals.unregister(name, self.menu.enqueue_state_event)

    def timeout(self):
        self.menu.pop()

    def render(self):
        with self.menu.display as d:
            d.font_size(3)
            d.puts(0, 0, 'Page {}'.format(self.__class__.__name__))

    def handle(self, ev):
        pass

    def handle_state_event(self, name, data):
        pass

    def __str__(self):
        return '<{} "{}">'.format(self.__class__.__name__, self.title)


class Deck(Page):
    """
    A collection of pages that an be cycled through with a key specified
    by next_page_evts,  similar to a deck of cards.
    """
    pages = []
    next_page_evts = [(Key.select, Action.short), (Key.select, Action.long)]

    def __init__(self):
        self.page_index = 0
        self.active_page = None

    def show(self, pos=0, from_child=None, **kwargs):
        if from_child is None:
            self.show_child(pos)
        super().show(**kwargs)

    def hide(self):
        if self.active_page:
            self.active_page.hide()
        super().hide()

    def show_child(self, idx):
        if idx > len(self.pages) - 1:
            self.page_index = 0
        else:
            self.page_index = idx

        if self.active_page:
            self.active_page.hide()

        self.active_page = self.pages[self.page_index]
        self.active_page.init(self.menu, self.state)
        self.active_page.show(render=False)

    def next_child(self):
        self.show_child(self.page_index + 1)
        self.render()

    def render(self):
        if self.active_page:
            self.active_page.render()

    def handle(self, ev):
        if (ev.name, ev.action) in self.next_page_evts:
            self.next_child()
            return True

        if self.active_page and self.active_page.handle(ev):
            return True

    def handle_state_event(self, name, data):
        if self.active_page:
            return self.active_page.handle_state_event(name, data)


class Slider(Page):
    minval = 0
    maxval = 100
    render_on_input = True

    def __init__(self):
        self.prevts = time.time()
        self.prevdir = 0

    @property
    def reverse_direction(self):
        return False

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
            val = self.get_value() + inc
            val = max(self.minval, min(self.maxval, val))
            self.set_value(val)
            if self.render_on_input:
                self.render()
            return True
        elif ev.pressed(Key.select):
            self.menu.pop()

    def get_value(self):
        return getattr(self, '_val', 0)

    def get_value_percent(self):
        return self.get_value()

    def set_value(self, val):
        self._val = val

    def render(self):
        val = self.get_value_percent()
        with self.menu.display as d:
            d.font_size(3)
            d.puts(13, 5, self.title)
            d.puts(116, 5, '{}%'.format(val), anchor='right')
            d.rect(13, 17, 115, 25)
            if val > 0:
                d.rect(14, 18, 14 + val, 24, fill=1)


class ValueListItem:
    label = 'ValueListItem'
    zero_value = None
    minval = 0
    maxval = 100

    def __init__(self):
        self.value = 0
        self.prevts = 0
        self.active = False

    def is_popup(self):
        return False

    def init(self, menu, state):
        self.menu = menu
        self.state = state

    def render_on(self, display, x, y, width):
        display.puts(x, y, self.get_label())
        value = self.get_value_display()
        if value is not None:
            display.puts(x + width, y, value, align='right', anchor='right')

    def hide(self):
        pass

    def show(self):
        pass

    def activate(self, parent):
        self.active = True

    def deactivate(self):
        self.active = False

    def is_active(self):
        return self.active

    def show_cursor(self):
        return not self.active

    def has_value(self):
        return True

    def get_value(self):
        return self.value

    def set_value(self, val):
        self.value = val

    def get_label(self):
        return self.label

    def format_value(self, val):
        return '{:3d}%'.format(val)

    def get_value_display(self):
        return '{}{}'.format(
            '>' if self.active else '',
            self.format_value(self.get_value()))

    def set_zero_value(self):
        self.set_value(self.zero_value)

    def handle(self, ev):
        if self.zero_value is not None and ev.long_pressed(Key.select):
            self.set_zero_value()
            return True
        if ev.name != Key.encoder:
            return
        inc = ev.value
        if self.prevts:
            diff = ev.ts - self.prevts
            if diff < 10000:
                inc *= 5
            elif diff < 50000:
                inc *= 2
        self.prevts = ev.ts
        val = self.get_value() + inc
        val = max(self.minval, min(self.maxval, val))
        self.set_value(val)
        return True


class BooleanListItem(ValueListItem):
    min = 0
    max = 1

    def __init__(self, state_obj, attribute, label):
        super().__init__()
        self.label = label
        self.attribute = attribute
        self.state_obj = state_obj

    def set_value(self, val):
        with self.state.lock():
            setattr(self.state_obj, self.attribute, (val == 1))

    def get_value(self):
        return 1 if getattr(self.state_obj, self.attribute) else 0

    def format_value(self, value):
        return 'On' if value else 'Off'

    def activate(self, parent):
        self.set_value(0 if self.get_value() else 1)

    def render_on(self, display, x, y, width):
        display.puts(x, y, self.get_label())
        char = chr(33) if self.get_value() else chr(32)
        display.font_size(9)
        display.puts(x + width, y, char, align='right', anchor='right')
        display.font_size(3)


class PopupItem:
    def __init__(self, label, page):
        self.label = label
        self.page = page

    def init(self, menu, state):
        self.menu = menu
        self.state = state

    def is_popup(self):
        return True

    def hide(self):
        pass

    def show(self):
        pass

    def render_on(self, display, x, y, width):
        display.puts(x, y, self.get_label())
        value = self.get_value_display()
        if value is not None:
            display.puts(x + width, y, value, align='right', anchor='right')

    def activate(self, parent):
        self.page.init(parent.menu, parent.state)
        parent.menu.push(self.page)

    def deactivate(self):
        self.menu.pop()

    def is_active(self):
        return self.page in self.menu.page_stack

    def show_cursor(self):
        return True

    def has_value(self):
        return False

    def get_label(self):
        return self.label

    def get_value_display(self):
        return None

    def handle(self, ev):
        return False


class ConfigList(Page):
    x_offset = 0

    def __init__(self, font_size=3, line_height=11, length=3, scrollbar=True):
        self.font_size = font_size
        self.line_height = line_height
        self.win_len = length
        self.scrollbar = scrollbar
        self.visible_items = []

    def get_items(self):
        return []

    def init(self, menu, state):
        super().init(menu, state)
        self.set_items(self.get_items())
        for item in self.items:
            item.init(menu, state)

    def hide(self):
        super().hide()
        for item in self.visible_items:
            item.hide()
        self.visible_items = []
        self.deactivate_active_item()

    def get_item(self):
        return self.items[self.pos]

    def toggle_item(self, item):
        if item.is_active():
            item.deactivate()
        else:
            item.activate(self)
        if item.has_value():
            self.render()

    def set_item_state(self, active):
        item = self.get_item()
        if item.is_active() != active:
            self.toggle_item(item)

    def timeout(self):
        self.deactivate_active_item()
        self.set_pos(0)
        super().timeout()

    def deactivate_active_item(self):
        item = self.get_item()
        if item.is_active():
            item.deactivate()

    def handle(self, ev):
        item = self.get_item()
        if item.is_active():
            if item.handle(ev):
                self.render()
                return True
            elif ev.pressed(Key.back):
                item.deactivate()
                if item.has_value():
                    self.render()
                return True

        if ev.name == Key.encoder:
            self.set_pos(self.pos + ev.value)
            self.render()
            return True
        if ev.pressed(Key.select):
            self.toggle_item(item)
            return True

    def set_items(self, items):
        self.items = items
        self.pos = 0
        self.win_start = 0
        self.win_end = min(len(self.items), self.win_len)

    def set_pos(self, pos):
        pos = max(0, min(len(self.items) - 1, pos))
        if self.pos != pos:
            self.pos = pos
            self.update_window()

    def update_window(self):
        if self.pos <= self.win_start:
            if self.pos > 0:
                self.win_start = self.pos - 1
                self.win_end = min(self.win_start + self.win_len,
                                   len(self.items))
            else:
                self.win_start = 0
                self.win_end = min(self.win_start + self.win_len,
                                   len(self.items))
        elif self.pos >= self.win_end - 1:
            if self.pos >= len(self.items) - 1:
                self.win_end = self.pos + 1
                self.win_start = max(0, self.win_end - self.win_len)
            else:
                self.win_end = self.pos + 2
                self.win_start = max(0, self.win_end - self.win_len)

    def render_items(self):
        display = self.menu.display
        win_pos = self.pos - self.win_start
        width = 117 - self.x_offset
        items = self.items[self.win_start:self.win_end]
        for visible_item in self.visible_items:
            if visible_item not in items:
                self.visible_items.remove(visible_item)
                visible_item.hide()
        for i, item in enumerate(items):
            y = i * self.line_height
            if i == win_pos and item.show_cursor():
                display.puts(self.x_offset, y, '>')
            if item not in self.visible_items:
                self.visible_items.append(item)
                item.show()
            item.render_on(display, self.x_offset + 6, y, width)

    def render_scollbar(self):
        if len(self.items) <= self.win_len:
            return
        per_item = 32 / len(self.items)
        length = math.ceil(per_item * self.win_len)
        top = int(self.win_start * per_item)
        bottom = top + length
        d = self.menu.display
        d.rect(126, top, 126, bottom)
        d.line(127, 0, 127, 31)

    def render(self):
        d = self.menu.display
        if not self.x_offset:
            d.clear()
        else:
            d.clear(self.x_offset, 0, 127, 31)
        d.font_size(self.font_size)
        self.render_items()
        if self.scrollbar:
            self.render_scollbar()
        d.update()


class ListPage(Page):
    x_offset = 0
    max_item_width = 0

    def __init__(self, items=None, font_size=3, length=3, scrollbar=True):
        self.cursor = 0
        self.highlight = -1
        self.font_size = font_size
        self.win_len = length
        self.scrollbar = scrollbar
        self.selected = None
        self.load_items(items)

    def load_items(self, items=None):
        self.set_items(items or [])

    def item_label(self, item):
        return item[1]

    def select_item(self, item):
        self.selected = item or self.get_cursor_item()
        self.menu.pop()

    def get_cursor_item(self):
        if self.items:
            return self.items[self.cursor]

    def handle(self, ev):
        if ev.name == Key.encoder:
            self.set_cursor(self.cursor + ev.value)
            self.render()
            return True
        if ev.pressed(Key.select):
            self.select_item(self.get_cursor_item())
            return True

    def set_items(self, items):
        self.items = items
        self.win_start = 0
        self.win_end = min(len(self.items), self.win_len)

    def set_cursor(self, idx):
        self.cursor = max(0, min(len(self.items) - 1, idx))
        self.update_window()

    def set_highlight(self, idx):
        self.highlight = max(-1, min(len(self.items) - 1, idx))

    def update_window(self):
        if self.cursor <= self.win_start:
            if self.cursor > 0:
                self.win_start = self.cursor - 1
                self.win_end = min(self.win_start + self.win_len,
                                   len(self.items))
            else:
                self.win_start = 0
                self.win_end = min(self.win_start + self.win_len,
                                   len(self.items))
        elif self.cursor >= self.win_end - 1:
            if self.cursor >= len(self.items) - 1:
                self.win_end = self.cursor + 1
                self.win_start = max(0, self.win_end - self.win_len)
            else:
                self.win_end = self.cursor + 2
                self.win_start = max(0, self.win_end - self.win_len)

    def render_items(self):
        d = self.menu.display
        font = d.get_font(self.font_size)
        win_pos = self.cursor - self.win_start
        for i, item in enumerate(self.items[self.win_start:self.win_end]):
            cursor_char = '>' if i == win_pos else ' '
            highlight = i + self.win_start == self.highlight
            if highlight:
                d.rect(self.x_offset, i * font.char_height, 124,
                       (i + 1) * font.char_height, fill=1)
            d.puts(self.x_offset, i * font.char_height + font.line_spacing,
                   cursor_char + self.item_label(item),
                   color=0 if highlight else 1)

    def render_scollbar(self):
        if len(self.items) <= self.win_len:
            return
        per_item = 32 / len(self.items)
        length = math.ceil(per_item * self.win_len)
        top = int(self.win_start * per_item)
        bottom = top + length
        self.menu.display.rect(126, top, 126, bottom)
        d = self.menu.display
        d.rect(126, top, 126, bottom)
        d.line(127, 0, 127, 31)

    def render(self):
        d = self.menu.display
        if not self.x_offset:
            d.clear()
        else:
            d.clear(self.x_offset, 0, 127, 31)
        d.font_size(self.font_size)
        self.render_items()
        if self.scrollbar:
            self.render_scollbar()
        d.update()


class TextInputPage(Page):
    chars = ' ABCDEFGHIJKLMNOPQRSTUVXXYZ abcdefghijklmnopqrstuvwxyz 0123456789 !()#'

    def __init__(self, title='Change:', max_length=20, input_line_y=20, font_size=3, text='',
                 callback=None):
        super().__init__()
        self.cursor = 0
        self.title = title
        self.max_length = max_length
        self.input_line_y = input_line_y
        self.font_size = font_size
        self.set_text(text)
        self.callback = callback

    def init(self, *args, **kwargs):
        super().init(*args, **kwargs)
        self.calculate_sizes()

    def set_text(self, text):
        self.input = [0] * self.max_length
        for i in range(min(len(text), self.max_length)):
            self.input[i] = max(self.chars.find(text[i]), 0)

    def get_text(self):
        text = ''.join(self.chars[i] for i in self.input)
        return text.rstrip()

    def calculate_sizes(self):
        d = self.menu.display
        font = d.get_font(self.font_size)
        self.max_chars = d.width // font.char_width
        self.num_chars = min(self.max_length, self.max_chars)
        self.x_offset = (d.width - (self.num_chars * font.char_width)) // 2
        self.input_y = self.input_line_y - font.char_height
        self.char_width = font.char_width

    def move_cursor(self, offset, carry_char=False):
        cursor = max(min(self.cursor + offset, self.max_length - 1), 0)
        if self.cursor != cursor:
            if carry_char and self.input[cursor] == 0:
                # carry over current char to next cursor pos
                self.input[cursor] = self.input[self.cursor]
            self.cursor = cursor
            self.render()

    def change_char(self, offset):
        char = (self.input[self.cursor] + offset) % len(self.chars)
        self.input[self.cursor] = char
        self.render()

    def del_char(self):
        if self.cursor == self.max_length - 1:
            self.input[-1] = 0
        else:
            self.input = self.input[:self.cursor] + self.input[self.cursor+1:] + [0]
        self.render()

    def handle(self, ev):
        if ev.pressed(Key.fn2):
            self.move_cursor(-1)
            return True
        if ev.pressed(Key.fn3):
            self.move_cursor(1)
            return True
        if ev.pressed(Key.select):
            self.move_cursor(1, carry_char=True)
            return True
        if ev.pressed(Key.fn1):
            self.del_char()
            return True
        if ev.name == Key.encoder:
            self.change_char(ev.value)
            return True
        if ev.pressed(Key.back):
            self.callback(self, False)
        if ev.name == Key.fn4 and ev.action == Action.down:
            if self.callback:
                self.callback(self, True)
            return True
        return True

    def render(self):
        button_labels = (
            (15, 'DEL'),
            (47, '<'),
            (80, '>'),
            (112, 'SAVE'),
        )
        with self.menu.display as d:
            d.font_size(self.font_size)

            # render current text
            d.puts(self.x_offset, self.input_y, self.get_text())

            # render the cursor and cursor char
            char = self.chars[self.input[self.cursor]]
            char_x = self.x_offset + self.cursor * self.char_width
            d.rect(char_x - 1, self.input_y - 1,
                   char_x + self.char_width - 1, self.input_line_y,
                   color=1, fill=1)
            d.puts(char_x, self.input_y, char, color=0)

            # render input line below text
            for i in range(self.num_chars):
                d.line(self.x_offset + i * self.char_width, self.input_line_y,
                       self.x_offset + ((i + 1) * self.char_width) - 2, self.input_line_y)

            d.font_size(1)
            d.puts(self.x_offset, 0, self.title)
            for x, label in button_labels:
                d.puts(x, 25, label, align='center', anchor='center')


class ChoicePage(ListPage):
    def __init__(self, callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callback = callback

    def select_item(self, item):
        self.callback(self, item[0])

    def handle(self, ev):
        if ev.pressed(Key.back):
            self.callback(self, None)
            return True

        super().handle(ev)
        return True
