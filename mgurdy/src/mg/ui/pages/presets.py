from .base import ListPage, TextInputPage, ChoicePage

from mg.input import Key
from mg.signals import signals

from mg.db import Preset


class PresetsPage(ListPage):
    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    def timeout(self):
        self.menu.goto('home')

    def show(self, from_child=None, render=True, **kwargs):
        self.load_presets()
        if not from_child:
            self.set_cursor(self.state.last_preset_number - 1)
        else:
            self.set_cursor(self.cursor)
        self.update_window()
        if render:
            self.render()

    def item_label(self, item):
        if item.number:
            return '{} {}'.format(item.number, item.name or 'Unnamed')
        else:
            return item.name or 'Unnamed'

    def select_item(self, item):
        if item.id:
            with self.menu.lock_state('Loading preset...'):
                self.state.load_preset(item.id)
            self.menu.goto('home')
        else:
            self.new_preset_show()

    def load_presets(self):
        presets = list(Preset.select())
        presets.append(Preset(name='New Preset...'))  # placeholder for 'new preset'
        self.set_items(presets)

    def delete_preset(self):
        preset = self.get_cursor_item()
        self.state.last_preset_number = 0
        preset.delete_instance()
        self.load_presets()
        self.menu.message('Preset deleted', popup=True, timeout=1)

    def handle(self, evt):
        if evt.long_pressed(Key.select):
            self.edit_choice_show()
            return True
        return super().handle(evt)

    def edit_choice_show(self):
        page = ChoicePage(self.edit_choice_callback, items=(
            ('move', 'Move'),
            ('rename', 'Rename'),
            ('replace', 'Overwrite'),
            ('delete', 'Delete'),
        ))
        self.menu.push(page)

    def edit_choice_callback(self, page, choice):
        self.menu.pop()
        if choice == 'rename':
            self.edit_name_show()
        elif choice == 'delete':
            self.delete_preset()
        elif choice == 'move':
            self.move_preset_show()
        elif choice == 'replace':
            self.replace_preset()

    def replace_preset(self):
        preset = self.get_cursor_item()
        self.state.save_preset(preset_id=preset.id)
        self.menu.message('Preset replaced', popup=True, timeout=1)

    def new_preset_show(self):
        page = TextInputPage(title='Add New Preset:',
                             text='Unnamed',
                             callback=self.new_preset_callback)
        self.menu.push(page)

    def new_preset_callback(self, textinput, confirm):
        self.menu.pop()
        if confirm:
            self.state.save_preset(name=textinput.get_text())
            self.menu.message('Preset added', popup=True, timeout=1)

    def edit_name_show(self):
        preset = self.get_cursor_item()
        page = TextInputPage(title='Rename Preset {}:'.format(preset.number),
                             text=preset.name,
                             callback=self.edit_name_callback)
        self.menu.push(page)

    def edit_name_callback(self, textinput, confirm):
        self.menu.pop()
        if confirm:
            preset = self.get_cursor_item()
            preset.name = textinput.get_text()
            preset.save()
            signals.emit('preset:changed', {'id': preset.id})
            self.menu.message('Changes saved', popup=True, timeout=1)

    def move_preset_show(self):
        preset = self.get_cursor_item()
        page = MovePresetPage(preset)
        self.menu.push(page)


class MovePresetPage(ListPage):
    def __init__(self, preset, *args, **kwargs):
        self.preset = preset
        super().__init__(*args, **kwargs)

    def show(self, from_child=None, render=True, **kwargs):
        # we only have messages as children, return to preset list
        if from_child:
            self.menu.pop()

        self.load_presets()
        if render:
            self.render()

    def item_label(self, item):
        return '{} {}'.format(item.number, item.name)

    def select_item(self, item):
        order = [item.id for item in self.items]
        self.state.preset.last_preset_number = 0
        Preset.reorder(order)
        signals.emit('preset:reordered', {'order': order})
        self.menu.message('Preset moved', popup=True, timeout=1)

    def handle(self, ev):
        if ev.pressed(Key.back):
            self.menu.message('Move cancelled', popup=True, timeout=1)
            return True
        super().handle(ev)
        return True

    def load_presets(self):
        presets = list(Preset.select())
        cursor = None
        for idx, preset in enumerate(presets):
            if preset.id == self.preset.id:
                cursor = idx
        self.set_items(presets)
        self.cursor = cursor
        self.highlight = cursor
        self.update_window()

    def set_cursor(self, pos):
        pos = max(0, min(len(self.items) - 1, pos))
        if self.cursor == pos:
            return

        self.items.insert(pos, self.items.pop(self.cursor))
        for idx, preset in enumerate(self.items):
            preset.number = idx + 1
        self.cursor = pos
        self.highlight = pos
        self.update_window()
