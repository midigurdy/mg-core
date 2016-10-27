from .base import PopupItem, ListPage, Deck, ConfigList, ValueListItem

from mg.input import Action, Key
from mg.utils import midi2percent, midi2note, PeriodicTimer


# used to synchronize the state of the voice param pages, so that the same parameter
# is selected when switching between strings / voices
VOICE_PARAM_STATE = {
    'pos': 0,
    'active': False
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


class PolyphonicItem(ValueListItem):
    label = 'Polyphonic'
    minval = 0
    maxval = 1

    def __init__(self, voice):
        super().__init__()
        self.voice = voice

    def set_value(self, val):
        with self.state.lock():
            self.voice.polyphonic = bool(val)

    def get_value(self):
        return int(self.voice.polyphonic)

    def format_value(self, value):
        return 'On' if value else 'Off'


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


class ModeItem(ValueListItem):
    label = 'Mode'
    minval = 0
    maxval = 2

    MODES = [
        ('midigurdy', 'MidiGurdy'),
        ('generic', 'Hurdy-Gurdy'),
        ('keyboard', 'Keyboard'),
    ]

    def __init__(self, voice):
        super().__init__()
        self.voice = voice

    def set_value(self, val):
        with self.state.lock():
            self.voice.mode = self.MODES[val][0]

    def get_value(self):
        return [m[0] for m in self.MODES].index(self.voice.mode)

    def format_value(self, value):
        return self.MODES[value][1]


class SoundPopupItem(PopupItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.x = 0
        self.y = 0
        self.diff = 1
        self.text_width = 0
        self.width = 0
        self.display = 0
        self.x_offset = 0
        self.scroll_wait = 0
        self.do_scroll = False
        self.timer = None

    def get_label(self):
        if self.page.voice.soundfont_id:
            sound = self.page.voice.get_sound()
            if sound:
                return '%s/%s' % (sound.name, sound.soundfont.name)
            else:
                return 'Missing: {} {}:{}'.format(
                    self.page.voice.soundfont_id,
                    self.page.voice.bank,
                    self.page.voice.program)

        else:
            return 'No sound...'

    def render_on(self, display, x, y, width):
        name = self.get_label()
        display.puts(x, y, name, max_width=width, x_offset=-self.x_offset)
        self.x = x
        self.y = y
        self.width = width
        self.text_width = len(name) * 6
        self.start_scroll()

    def update_scroll(self):
        d = self.menu.display
        if self.x_offset > self.text_width - self.width and self.diff != -1:
            self.diff = -1
            self.scroll_wait = 10
        if self.x_offset < 0 and self.diff != 1:
            self.diff = 1
            self.scroll_wait = 10
        self.scroll_wait -= 1
        if self.scroll_wait > 0:
            return
        self.x_offset += self.diff
        with self.menu.page_lock:
            d.rect(self.x, self.y, self.x + self.width, self.y + 11, color=0, fill=0)
            self.render_on(d, self.x, self.y, self.width)
            d.update()

    def hide(self):
        self.stop_scroll()

    def show(self):
        self.do_scroll = True
        self.start_scroll()

    def start_scroll(self):
        with self.menu.page_lock:
            if not self.do_scroll:
                return
            if self.timer is not None or self.text_width <= self.width:
                return
            self.x_offset = 0
            self.scroll_wait = 10
            self.timer = PeriodicTimer(0.08, self.update_scroll)
            self.timer.start()

    def stop_scroll(self):
        with self.menu.page_lock:
            self.do_scoll = False
            if self.timer:
                self.timer.stop()
                self.timer = None


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
        for i, (inum, sf, sound) in enumerate(items):
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
            for i, (inum, sf, sound) in enumerate(items):
                if (sf and sf.id == self.voice.soundfont_id):
                    cursor_pos = i
                    break
        else:
            cursor_pos = self.sf_cursor
        self.set_cursor(cursor_pos)
        self.sf_cursor = cursor_pos

    def show_sounds(self, sf):
        items = []
        for i, sound in enumerate(sf.sounds):
            if ((sf.mode == 'generic' and not self.limit_to_type) or
                    (sf.mode == 'midigurdy' and sound.type == self.voice.type)):
                items.append((i + 1, sf, sound))
        self.set_items(items)

        cursor_pos = 0
        # if we are showing the currently active soundfont, put the cursor
        # on the sound that is currently selected on the voice
        if self.voice.soundfont_id == sf.id:
            for i, (inum, sf, sound) in enumerate(items):
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
            self.menu.pop()
        elif snum == -1:
            with self.state.lock():
                self.voice.clear_sound()
                self.voice.muted = True
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
            SoundPopupItem('Sound...', TreeSoundListPage(self.voice)),
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
            PolyphonicItem(self.voice),
            ModeItem(self.voice),
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
            SoundPopupItem('Sound...', TreeSoundListPage(self.voice, x_offset=0, limit_to_type=True)),
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
