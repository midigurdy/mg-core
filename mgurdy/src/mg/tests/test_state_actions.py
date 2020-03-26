from queue import Queue
import pytest

from mg.db import initialize, Preset
from mg.handler import StateActionHandler
from mg.input.events import Event
from mg.state import State
from mg.ui.display.base import BaseDisplay
from mg.ui.menu import Menu
from mg.ui.pages.base import Page
from mg.tests.conf import settings


@pytest.fixture
def handler(tmpdir):
    display = BaseDisplay(128, 32)
    event_queue = Queue()
    state = State(settings)
    menu = Menu(event_queue, state, display)
    handler = StateActionHandler(state, menu)
    yield handler
    menu.cleanup()


@pytest.fixture
def db():
    initialize(':memory:')


def test_load_preset(db, handler):
    p = Preset.create(name='P1')
    # load preset shows a loading page, so we need a home to return
    # back to...
    handler.menu.register_page('home', Page)

    assert handler.state.last_preset_number == 0

    handler.load_preset(_evt('', '', p.number))

    assert handler.state.last_preset_number == p.number


def test_toggle_string_mute(handler):
    assert handler.state.preset.melody[0].muted is True

    handler.toggle_string_mute(_evt('', '', 0))

    assert handler.state.preset.melody[0].muted is False


def _evt(name, action='down', value=None):
    return Event.from_mapping({
        'type': 'state_action',
        'name': name,
        'value': value,
    })
