import pytest

from mg.server.app import app as flask_app
from mg.tests.conf import settings
from mg.state import State


@pytest.fixture
def client():
    flask_app.config['state'] = State(settings)
    return flask_app.test_client()


@pytest.fixture
def webroot(tmpdir):
    settings.webroot_dir = str(tmpdir)
    return tmpdir


def test_get_static_file(client, webroot):
    webroot.ensure('static', dir=True).join('test.js').write('testing')

    rv = client.get('/static/test.js')

    assert rv.status_code == 200
    assert rv.data == b'testing'


def test_get_favicon(client, webroot):
    webroot.ensure('static', dir=True).join('favicon.ico').write('testing')

    rv = client.get('/favicon.ico')

    assert rv.status_code == 200
    assert rv.data == b'testing'


def test_get_index(client, webroot):
    webroot.join('index.html').write('testing')

    rv = client.get('/')

    assert rv.status_code == 200
    assert rv.data == b'testing'


def test_get_any_other_file_returns_index(client, webroot):
    webroot.join('index.html').write('testing')

    rv = client.get('/blafoo/test')

    assert rv.status_code == 200
    assert rv.data == b'testing'
