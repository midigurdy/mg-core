import pytest

from mg.tests.conf import settings
from mg.state import State
from mg.ui.menu import Menu
from mg.ui.pages.base import Page
from mg.ui.display.base import BaseDisplay


@pytest.fixture(scope='module')
def display():
    return BaseDisplay(128, 32)


def test_register_and_goto_named_page(display):
    menu = Menu(None, State(settings), display)

    menu.register_page('test', Page)
    menu.goto('test')
    menu.cleanup()
