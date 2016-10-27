import json
import pytest

from mg.db import initialize
from mg.server.app import app as flask_app
from mg.state import State


@pytest.fixture
def db():
    initialize(':memory:')


@pytest.fixture
def client(db):
    flask_app.config['state'] = State()
    return flask_app.test_client()


def rjson(response):
    return json.loads(response.data.decode('utf8'))


def test_fetch_default_calibration(client):
    rv = client.get('/api/calibrate/keyboard')
    data = rjson(rv)
    assert rv.status_code == 200
    assert len(data) == 24  # one entry for each key
    assert 'pressure' in data[0]
    assert 'velocity' in data[0]


def test_restore_to_default(client):
    rv = client.delete('/api/calibrate/keyboard')
    data = rjson(rv)
    assert rv.status_code == 200
    assert len(data) == 24  # one entry for each key
    assert 'pressure' in data[0]
    assert 'velocity' in data[0]


def test_save_and_read_calibration(client):
    data = [{'pressure': 1, 'velocity': 2}] * 24

    rv = client.put('/api/calibrate/keyboard', data=json.dumps(data),
                    content_type='application/json')
    result = rjson(rv)
    assert rv.status_code == 200
    assert result == data

    rv = client.get('/api/calibrate/keyboard')
    result = rjson(rv)
    assert rv.status_code == 200
    assert result == data
