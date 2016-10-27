from queue import Queue
import pytest
import os

from mg.ui.display.base import BaseDisplay
from mg.ui.menu import Menu
from mg.ui.pages.base import Page
from mg.signals import signals
from mg.db import initialize, Preset
from mg.state import State, VoiceState
from mg.conf import settings
from mg.sf2 import SoundFont

signals.propagate_exceptions = True


@pytest.fixture
def menu(tmpdir):
    display = BaseDisplay(128, 32)
    event_queue = Queue()
    menu = Menu(event_queue, State(), display)
    yield menu
    menu.cleanup()


@pytest.fixture
def db():
    initialize(':memory:')


@pytest.fixture
def testdata_dir():
    settings.sound_dir = get_testdata_dir()
    return settings.data_dir


def get_testdata_dir():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, 'data')


def test_signal_reaches_page(menu):

    class TestPage(Page):
        state_events = ['test:blafoo']

    menu.register_page('test', TestPage)
    menu.goto('test')

    signals.emit('test:blafoo', {'val': 'test123'})


def test_save_and_load_state_as_preset(db, menu):
    assert Preset.select().count() == 0

    menu.state.clear()

    menu.state.preset.melody[0].soundfont_id = 'mg.sf2'
    menu.state.preset.melody[0].bank = 1
    menu.state.preset.melody[0].prog = 2

    menu.state.save_preset()

    assert Preset.select().count() == 1
    preset = Preset.get()
    assert preset.name == 'Unnamed'
    assert preset.number == 1

    menu.state.clear()
    menu.state.load_preset(preset.id)

    assert menu.state.preset.melody[0].soundfont_id == 'mg.sf2'
    assert menu.state.preset.melody[0].bank == 1
    assert menu.state.preset.melody[0].prog == 2


def test_set_sound_on_voice(db, menu, testdata_dir):
    sf = SoundFont.by_id('mg.sf2')
    sound = sf.get_sound(0, 1)
    voice = VoiceState('melody')
    voice.set_sound(sound)

    assert voice.soundfont_id == 'mg.sf2'
    assert voice.type == 'melody'
    assert voice.bank == 0
    assert voice.program == 1
    assert voice.get_sound() is not None
