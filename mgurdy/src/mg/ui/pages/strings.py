from .base import PopupItem, ListPage, Deck, ConfigList, ValueListItem, BooleanListItem

from mg.input import Action, Key
from mg.utils import midi2percent, midi2note


# used to synchronize the state of the voice param pages, so that the same parameter
# is selected when switching between strings / voices
VOICE_PARAM_STATE = {
    'pos': 0,
    'active': False,
}


class VoiceParamItem(ValueListItem):
    minval = 0
    maxval = 127

    def __init__(self, voice, param, label):
        super().__init__()
        self.label = label
        self.voice = voice
        self.param = param

    def set_value(self, val):
        # remove equal percent steps due to rounding errors
        if self.value != val and midi2percent(self.value) == midi2percent(val):
            val += 1 if self.value < val else -1
        with self.state.lock():
            setattr(self.voice, self.param, val)
        self.value = val

    def get_value(self):
        self.value = getattr(self.voice, self.param)
        return self.value

    def format_value(self, val):
        return '{:3d}%'.format(midi2percent(val))


class VoicePanningItem(ValueListItem):
    label = 'Balance'
    zero_value = 64
    minval = 0
    maxval = 127

    def __init__(self, voice):
        super().__init__()
        self.voice = voice

    def set_value(self, val):
        with self.state.lock():
            self.voice.panning = val

    def get_value(self):
        return self.voice.panning

    def format_value(self, value):
        if value == 64:
            return 'Center'
        if value == 127:
            return 'Rght 100%'
        pan = int(round((value - 64) * (100 / 64.0)))
        return '{} {}%'.format(
            'Left' if pan < 0 else 'Right',
            -pan if pan < 0 else pan)


class BaseNoteItem(ValueListItem):
    label = 'Note'
    zero_value = True
    minval = 0
    maxval = 127

    def __init__(self, voice):
        super().__init__()
        self.voice = voice

    def set_value(self, val):
        with self.state.lock():
            self.voice.base_note = val

    def set_zero_value(self):
        snd = self.voice.get_sound()
        if snd and snd.base_note >= 0:
            self.set_value(snd.base_note)
        else:
            self.set_value(60)

    def get_value(self):
        return self.voice.base_note

    def format_value(self, value):
        return midi2note(value)


class CapoItem(ValueListItem):
    label = 'Capo'
    minval = 0
    maxval = 23

    def __init__(self, voice):
        super().__init__()
        self.voice = voice

    def set_value(self, val):
        with self.state.lock():
            self.voice.capo = val

    def get_value(self):
        return self.voice.capo

    def format_value(self, value):
        return 'Off' if not value else 'Key %d' % value


class FineTuneItem(ValueListItem):
    label = 'Fine Tune'
    zero_value = 0
    minval = -100
    maxval = 100

    def __init__(self, voice):
        super().__init__()
        self.voice = voice

    def format_value(self, val):
        return '{}{} Ct'.format('+' if val > 0 else '', val)

    def set_value(self, val):
        self.voice.finetune = val

    def get_value(self):
        return self.voice.finetune


class KeyboardModeItem(ValueListItem):
    label = 'Keyboard Mode'
    min = 0
    max = 1

    def __init__(self, voice):
        super().__init__()
        self.voice = voice

    def set_value(self, val):
        if self.voice.has_midigurdy_soundfont():
            return
        with self.state.lock():
            self.voice.mode = 'keyboard' if val == 1 else 'midigurdy'

    def get_value(self):
        return 1 if self.voice.mode == 'keyboard' else 0

    def format_value(self, value):
        return 'On' if value else 'Off'

    def activate(self, parent):
        self.set_value(0 if self.get_value() else 1)

    def render_on(self, display, x, y, width):
        display.puts(x, y, self.get_label())
        if self.voice.has_midigurdy_soundfont():
            display.puts(x + width, y, 'N/A', align='right', anchor='right')
        else:
            char = chr(33) if self.get_value() else chr(32)
            display.font_size(9)
            display.puts(x + width, y, char, align='right', anchor='right')
            display.font_size(3)


class SoundPopupItem(PopupItem):
    def get_label(self):
        voice = self.page.voice
        prev_snd = getattr(self, '_prev_snd', (-1, -1, -1))
        cur_snd = (voice.soundfont_id, voice.bank, voice.program)
        if prev_snd != cur_snd:
            # Label creation cached to prevent unnessecary calls to
            # VoiceState.get_sound() (which parses the SF2 file every time)
            if voice.soundfont_id:
                sound = voice.get_sound()
                if sound:
                    self._label = '%s/%s' % (sound.name, sound.soundfont.name)
                else:
                    self._label = 'Missing: {} {}:{}'.format(
                        voice.soundfont_id,
                        voice.bank,
                        voice.program)
            else:
                self._label = 'No sound' + chr(127)
            self._prev_snd = cur_snd
        return self._label

    def render_on(self, display, x, y, width):
        name = self.get_label()
        display.scrolltext(x, y, width, name, initial_delay=500, shift_delay=80, end_delay=500)


class SoundListPage(ListPage):
    x_offset = 14
    max_item_width = 120

    def __init__(self, voice, *args, **kwargs):
        self.voice = voice
        self.limit_to_type = kwargs.pop('limit_to_type', False)
        if 'x_offset' in kwargs:
            self.x_offset = kwargs.pop('x_offset')
        super().__init__(*args, **kwargs)

    def show(self, render=True, **kwargs):
        from mg.sf2 import SoundFont

        self.font_size = 3
        self.win_len = 3
        soundfonts = SoundFont.load_all()

        items = [(-1, None, None)]
        for sf in [obj for obj in soundfonts if obj.mode != 'generic']:
            sounds = []
            for i, sound in enumerate(sf.sounds):
                if sound.type == self.voice.type:
                    sounds.append((i + 1, sf, sound))
            if sounds:
                items.append((0, sf, None))
                items.extend(sounds)
        if not self.limit_to_type:
            for sf in [obj for obj in soundfonts if obj.mode == 'generic']:
                sounds = []
                for i, sound in enumerate(sf.sounds):
                    sounds.append((i + 1, sf, sound))
                if sounds:
                    items.append((0, sf, None))
                    items.extend(sounds)
        pos = 0
        voice = self.voice
        for i, (_inum, sf, sound) in enumerate(items):
            if sound is None:
                continue
            if (sf.id == voice.soundfont_id and sound.bank == voice.bank and
                    sound.program == voice.program):
                pos = i
                break
        self.set_items(items)
        self.set_cursor(pos)
        if render:
            self.render()

    def handle(self, ev):
        if ev.name == Key.encoder:
            pos = self.cursor + ev.value
            pos = max(0, min(len(self.items) - 1, pos))
            if pos != self.cursor:
                if self.items[pos][2] is None:
                    pos += ev.value
            self.set_cursor(pos)
            self.render()
            return True
        return super().handle(ev)

    def item_label(self, item):
        snum, sf, sound = item
        if sound:
            return '{} {}'.format(snum, sound.name)
        elif sf:
            return sf.name
        else:
            return ' - No sound -'

    def select_item(self, item):
        snum, sf, sound = item
        if sound:
            with self.menu.lock_state('Loading...'):
                unmute = not self.voice.soundfont_id
                self.voice.set_sound(sound)
                # only unmute if the string didn't have a sound
                # before setting the new sound
                if unmute:
                    self.voice.muted = False
        elif snum == -1:
            with self.state.lock():
                self.voice.clear_sound()
                self.voice.muted = True
        self.menu.pop()

    def render_items(self):
        d = self.menu.display
        d.font_size(3)
        win_pos = self.cursor - self.win_start
        items = []
        for i, item in enumerate(self.items[self.win_start:self.win_end]):
            snum, sf, sound = item
            if i == win_pos:
                marker = '>' if (sound or snum == -1) else ' '
            else:
                marker = ' '
            spacer = ''
            if i == 0 and sound:
                items.append(marker + sf.name)
            else:
                items.append(spacer + marker + self.item_label(item))
                if sound is None and snum != -1:
                    for x in range(self.x_offset + 3, 123, 2):
                        self.menu.display.line(x, (i * 11) + 9, x, (i * 11) + 9)
            if i == 0 and snum != -1:
                for x in range(self.x_offset + 3, 123, 2):
                    self.menu.display.line(x, (i * 11) + 9, x, (i * 11) + 9)
        self.menu.display.puts(self.x_offset, 0, '\n'.join(items),
                               max_width=self.max_item_width - self.x_offset)


class TreeSoundListPage(ListPage):
    x_offset = 14
    max_item_width = 120

    def __init__(self, voice, *args, **kwargs):
        self.voice = voice
        self.limit_to_type = kwargs.pop('limit_to_type', False)
        self.x_offset = kwargs.pop('x_offset', self.x_offset)

        self.sf_cursor = -1
        self.selected_sf = None

        super().__init__(*args, **kwargs)

    def show_soundfonts(self):
        from mg.sf2 import SoundFont
        soundfonts = SoundFont.load_all()
        items = [(-1, None, None)]
        # only append midigurdy soundfonts if they contain at least one
        # sound of the current voice type
        for sf in [obj for obj in soundfonts if obj.mode != 'generic']:
            found = False
            for snd in sf.sounds:
                if snd.type == self.voice.type:
                    found = True
                    break
            if found:
                items.append((0, sf, None))
        if not self.limit_to_type:
            for sf in [obj for obj in soundfonts if obj.mode == 'generic']:
                items.append((0, sf, None))
        self.set_items(items)

        if self.sf_cursor == -1:
            cursor_pos = 0
            for i, (_inum, sf, _sound) in enumerate(items):
                if (sf and sf.id == self.voice.soundfont_id):
                    cursor_pos = i
                    break
        else:
            cursor_pos = self.sf_cursor
        self.set_cursor(cursor_pos)
        self.sf_cursor = cursor_pos

    def show_sounds(self, sf):
        items = []
        i = 1
        for sound in sf.sounds:
            if ((sf.mode == 'generic' and not self.limit_to_type) or
                    (sf.mode == 'midigurdy' and sound.type == self.voice.type)):
                items.append((i, sf, sound))
                i += 1
        self.set_items(items)

        cursor_pos = 0
        # if we are showing the currently active soundfont, put the cursor
        # on the sound that is currently selected on the voice
        if self.voice.soundfont_id == sf.id:
            for i, (_inum, _sf, sound) in enumerate(items):
                if (sound.bank == self.voice.bank and
                        sound.program == self.voice.program):
                    cursor_pos = i
                    break
        self.set_cursor(cursor_pos)

    def show(self, render=True, **kwargs):
        self.font_size = 3
        self.win_len = 3

        if self.selected_sf:
            self.show_sounds(self.selected_sf)
        else:
            self.show_soundfonts()
        if render:
            self.render()

    def handle(self, ev):
        if ev.name == Key.encoder:
            pos = self.cursor + ev.value
            pos = max(0, min(len(self.items) - 1, pos))
            self.set_cursor(pos)
            self.render()
            return True
        if ev.pressed(Key.back) and self.selected_sf:
            self.selected_sf = None
            self.show_soundfonts()
            self.set_cursor(self.sf_cursor)
            self.render()
            return True
        return super().handle(ev)

    def item_label(self, item):
        snum, sf, sound = item
        if sound:
            return '{} {}'.format(snum, sound.name)
        elif sf:
            return sf.name
        else:
            return ' - No sound -'

    def select_item(self, item):
        snum, sf, sound = item
        if sound:
            with self.menu.lock_state('Loading...'):
                unmute = not self.voice.soundfont_id
                self.voice.set_sound(sound)
                # only unmute if the string didn't have a sound
                # before setting the new sound
                if unmute:
                    self.voice.muted = False
            self.selected_sf = None
            self.menu.pop()
        elif snum == -1:
            with self.state.lock():
                self.voice.clear_sound()
                self.voice.muted = True
            self.selected_sf = None
            self.menu.pop()
        else:
            self.selected_sf = sf
            self.sf_cursor = self.cursor
            self.show_sounds(sf)
            self.render()

    def render_itemsa(self):
        d = self.menu.display
        d.font_size(3)
        win_pos = self.cursor - self.win_start
        items = []
        for i, item in enumerate(self.items[self.win_start:self.win_end]):
            snum, sf, sound = item
            if i == win_pos:
                marker = '>' if (sound or snum == -1) else ' '
            else:
                marker = ' '
            spacer = ''
            if i == 0 and sound:
                items.append(marker + sf.name)
            else:
                items.append(spacer + marker + self.item_label(item))
        self.menu.display.puts(self.x_offset, 0, '\n'.join(items),
                               max_width=self.max_item_width - self.x_offset)


class VoicePage(ConfigList):
    x_offset = 14

    def __init__(self, title, voice_name, *args, **kwargs):
        self.title = title
        self.voice_name = voice_name
        self.sync_state = kwargs.pop('sync_state', True)
        super().__init__(*args, **kwargs)

    def init(self, menu, state):
        self.voice = state.obj_by_path(self.voice_name)
        super().init(menu, state)

    def show(self, *args, **kwargs):
        if self.sync_state:
            self.set_pos(VOICE_PARAM_STATE['pos'])
            if not self.get_item().is_popup():
                self.set_item_state(VOICE_PARAM_STATE['active'])
        super().show(*args, **kwargs)

    def get_items(self):
        return [
            SoundPopupItem('Sound' + chr(127), TreeSoundListPage(self.voice)),
            BaseNoteItem(self.voice),
            VoiceParamItem(self.voice, 'volume', 'Volume'),
            VoicePanningItem(self.voice),
            FineTuneItem(self.voice),
        ]

    def set_pos(self, pos):
        super().set_pos(pos)
        if self.sync_state:
            VOICE_PARAM_STATE['pos'] = pos

    def toggle_item(self, item):
        super().toggle_item(item)
        if self.sync_state:
            VOICE_PARAM_STATE['active'] = item.is_active()

    def deactivate_active_item(self):
        super().deactivate_active_item()
        if self.sync_state:
            VOICE_PARAM_STATE['active'] = False


class MelodyPage(VoicePage):
    def get_items(self):
        return super().get_items() + [
            CapoItem(self.voice),
            BooleanListItem(self.voice, 'polyphonic', 'Polyphonic'),
            KeyboardModeItem(self.voice),
        ]


class KeynoisePage(VoicePage):
    x_offset = 0

    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    def timeout(self):
        self.menu.goto('home')

    def get_items(self):
        return [
            SoundPopupItem('Sound' + chr(127), TreeSoundListPage(self.voice, x_offset=0, limit_to_type=True)),
            VoiceParamItem(self.voice, 'volume', 'Volume'),
            VoicePanningItem(self.voice),
        ]


class VoiceDeck(Deck):

    @property
    def idle_timeout(self):
        return self.state.ui.timeout

    def timeout(self):
        self.active_page.timeout()

    def render(self):
        d = self.menu.display
        d.clear()
        d.font_size(1)
        for i, page in enumerate(self.pages):
            if page == self.active_page:
                d.rect(0, i * 11, 11, (i + 1) * 11 - 2, color=1, fill=1)
                d.puts(1, 2 + i * 11, page.title, color=0)
            else:
                d.puts(1, 2 + i * 11, page.title)
            d.line(12, 0, 12, 32)
        super().render()


class MelodyDeck(VoiceDeck):
    next_page_evts = [(Key.fn2, Action.short), (Key.fn2, Action.long)]

    pages = [
        MelodyPage(title='M1', voice_name='preset.melody.0'),
        MelodyPage(title='M2', voice_name='preset.melody.1'),
        MelodyPage(title='M3', voice_name='preset.melody.2'),
    ]


class DroneDeck(VoiceDeck):
    next_page_evts = [(Key.fn1, Action.short), (Key.fn1, Action.long)]

    pages = [
        VoicePage(title='D1', voice_name='preset.drone.0'),
        VoicePage(title='D2', voice_name='preset.drone.1'),
        VoicePage(title='D3', voice_name='preset.drone.2'),
    ]


class TrompetteDeck(VoiceDeck):
    next_page_evts = [(Key.fn3, Action.short), (Key.fn3, Action.long)]

    pages = [
        VoicePage(title='T1', voice_name='preset.trompette.0'),
        VoicePage(title='T2', voice_name='preset.trompette.1'),
        VoicePage(title='T3', voice_name='preset.trompette.2'),
    ]
