import json
import pytest

from mg.tests.conf import settings
from mg.server.app import app as flask_app
from mg.state import State


@pytest.fixture
def state():
    return State(settings)


@pytest.fixture
def client(state):
    flask_app.config['state'] = state
    return flask_app.test_client()


def rjson(response):
    return json.loads(response.data.decode('utf8'))


def test_get_instrument_state(client, state):
    state.clear()

    rv = client.get('/api/instrument')

    expected = {
        'main': {'gain': 50, 'volume': 120, 'pitchbend_range': 0},
        'tuning': {'coarse': 0, 'fine': 0},
        'reverb': {'volume': 25, 'panning': 64},
        'keynoise': {'volume': 20, 'panning': 64, 'soundfont': None, 'bank': 0, 'program': 0},
        'voices': {
            'melody': [
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                },
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                },
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                }
            ],
            'drone': [
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                },
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                },
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                }
            ],
            'trompette': [
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                },
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                },
                {
                    'bank': 0,
                    'note': 60,
                    'capo': 0,
                    'mode': 'midigurdy',
                    'muted': True,
                    'panning': 64,
                    'polyphonic': False,
                    'program': 0,
                    'soundfont': None,
                    'volume': 100,
                    'finetune': 0,
                    'chien_threshold': 50,
                }
            ]
        },
    }

    assert rjson(rv) == expected
    assert rv.status_code == 200


def test_partial_update_instrument_state(client, state):
    data = {
        'tuning': {'coarse': 42},
    }

    state.main_volume = 1
    state.preset.melody[0].soundfont_id = 'blafoo'

    rv = client.put('/api/instrument', data=json.dumps(data),
                    content_type='application/json')

    assert rv.status_code == 200
    assert state.coarse_tune == 42
    assert state.main_volume == 1
    assert state.preset.melody[0].soundfont_id == 'blafoo'


def test_full_update_instrument_state(client, state):
    data = {
        'tuning': {'coarse': 42},
    }

    state.main_volume = 1
    state.preset.melody[0].soundfont_id = 'blafoo'

    rv = client.post('/api/instrument', data=json.dumps(data),
                     content_type='application/json')

    assert rv.status_code == 200
    assert state.coarse_tune == 42
    assert state.main_volume == 120  # default value
    assert state.preset.melody[0].soundfont_id is None
