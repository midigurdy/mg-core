import pytest
import mock
import os

from mg.input.events import Event
from mg.ui.display import Display
from mg.ui.menu import Menu
from mg.ui.pages.base import Page
from mg.conf import settings

import mg.ui.pages.main as main_pages
import mg.ui.pages.strings as string_pages
from mg.state import State, VoiceState


@pytest.fixture
def menu(tmpdir):
    output = tmpdir.join('output').ensure()
    display = Display(128, 32, str(output))
    menu = Menu(None, State(), display)

    class Home(Page):
        title = 'MockHome'

    menu.register_page('home', Home)
    yield menu
    menu.cleanup()


@pytest.fixture
def testdata_dir():
    settings.sound_dir = get_testdata_dir()
    return settings.data_dir


def get_testdata_dir():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, 'data')


@mock.patch('mg.fluidsynth.api.lib', mock.Mock(**{
        'get_cpu_load.return_value': 1.1,
}))
def test_goto_main_home(menu):
    menu.goto(main_pages.Home())


def test_goto_main_volume(menu):
    menu.goto(main_pages.VolumeDeck())


def test_sound_list_page(menu, testdata_dir):
    voice = VoiceState('melody')
    page = string_pages.SoundListPage(voice=voice)
    menu.push(page)
    page.render()


def _evt(name, action='down', value=None):
    return Event.from_mapping({
        'type': 'input',
        'name': name,
        'action': action,
        'value': value,
    })
