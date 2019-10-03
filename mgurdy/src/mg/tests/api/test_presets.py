import json
import pytest

from mg.db import initialize, Preset
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


def test_list_empty_presets(client):
    rv = client.get('/api/presets')
    assert rjson(rv) == []
    assert rv.status_code == 200


def test_list_presets(client):
    p1 = Preset(name='p1')
    p1.set_data({
        'voices': {
            'melody': [
                {
                    'soundfont': 'test',
                }
            ],
            'drone': [],
            'trompette': [],
        }
    })
    p1.save()

    Preset.create(name='p2', data='{}')

    rv = client.get('/api/presets')

    assert rjson(rv) == [
        {
            'id': 1,
            'name': 'p1',
            'number': 1,
            'voices': {
                'melody': [{
                    'soundfont': 'test',
                    'bank': 0,
                    'program': 0,
                    'note': 60,
                    'polyphonic': False,
                    'muted': True,
                    'capo': 0,
                    'volume': 127,
                    'panning': 64,
                    'mode': 'midigurdy',
                    'finetune': 0,
                    'chien_threshold': 50,
                }],
                'trompette': [],
                'drone': [],
            }
        },
        {
            'id': 2,
            'name': 'p2',
            'number': 2,
        },
    ]

    assert rv.status_code == 200


def test_get_preset(client):
    Preset.create(name='p1', data='{}')

    rv = client.get('/api/presets/1')

    expected = {
        'id': 1,
        'name': 'p1',
        'number': 1,
    }

    assert rjson(rv) == expected
    assert rv.status_code == 200


def test_create_preset(client):
    assert len(Preset.select()) == 0

    data = {
        'name': 'p1',
        'voices': {
            'melody': [
                {
                    'soundfont': 'test',
                    'bank': 0,
                    'program': 0,
                    'note': 60,
                    'polyphonic': False,
                    'muted': False,
                    'capo': 1,
                    'volume': 2,
                    'panning': 0,
                    'mode': 'midigurdy',
                    'finetune': 0,
                    'chien_threshold': 50,
                }, {
                    'soundfont': 'test',
                    'bank': 0,
                    'program': 1,
                    'note': 61,
                    'polyphonic': False,
                    'muted': False,
                    'capo': 2,
                    'volume': 3,
                    'panning': 100,
                    'mode': 'keyboard',
                    'finetune': 0,
                    'chien_threshold': 50,
                }
            ],
            'drone': [],
            'trompette': [],
        },
    }

    rv = client.post('/api/presets',
                     data=json.dumps(data),
                     content_type='application/json')

    expected = dict(data)
    expected['id'] = 1
    expected['number'] = 1

    assert rv.status_code == 201
    assert rjson(rv) == expected
    assert len(Preset.select(Preset.id == 1)) == 1


def test_create_preset_without_payload_returns_error(client):
    rv = client.post('/api/presets')

    assert rv.status_code == 400


def test_create_preset_checks_max_voice_len(client):
    voice = {
        'soundfont': 'test.sf2',
        'bank': 0,
        'program': 1,
        'note': 60,
        'polyphonic': False,
        'muted': False,
        'capo': 1,
        'volume': 2,
        'panning': 0,
        'finetune': 0,
        'chien_threshold': 50,
    }
    data = {
        'name': 'p1',
        'voices': {
            'melody': [voice, voice, voice, voice],
            'drone': [voice, voice, voice, voice],
            'trompette': [voice, voice, voice, voice],
        },
    }

    rv = client.post('/api/presets', data=json.dumps(data),
                     content_type='application/json')

    expected = {
        'errors': {
            'voices': {
                'trompette': ['Longer than maximum length 3.'],
                'drone': ['Longer than maximum length 3.'],
                'melody': ['Longer than maximum length 3.']
            }
        }
    }

    assert rv.status_code == 400
    assert rjson(rv) == expected
    assert Preset.select().count() == 0


def test_delete_preset(client):
    Preset.create(name='p1')

    assert Preset.select().count() == 1

    rv = client.delete('/api/presets/1')

    assert rv.status_code == 204
    assert Preset.select().count() == 0


def test_delete_reorders_presets(client):
    p1 = Preset.create(name='p1')
    Preset.create(name='p2')
    p3 = Preset.create(name='p3')

    rv = client.delete('/api/presets/2')

    assert rv.status_code == 204
    assert Preset.select().count() == 2
    assert Preset.get(Preset.id == p1.id).number == 1
    assert Preset.get(Preset.id == p3.id).number == 2


def test_load_preset(client):
    Preset.create(name='p1')
    Preset.create(name='p2')
    Preset.create(name='p3')

    rv = client.post('/api/presets/3/load')

    assert rv.status_code == 204


def test_order_presets(client):
    Preset.create(name='p1')
    Preset.create(name='p2')
    Preset.create(name='p3')

    order = [3, 1, 2]

    rv = client.post('/api/presets/order',
                     data=json.dumps({'order': order}),
                     content_type='application/json')

    assert rv.status_code == 200
    assert rjson(rv) == {'order': order}

    assert Preset.get(Preset.id == 3).number == 1
    assert Preset.get(Preset.id == 1).number == 2
    assert Preset.get(Preset.id == 2).number == 3


def test_update_preset(client):
    p = Preset(name='p1')
    p.set_data({
        'voices': {
            'melody': [
                {
                    'soundfont': 'test',
                }
            ],
            'drone': [
                {
                    'soundfont': 'test',
                    'program': 1,
                    'note': 61,
                }
            ],
        }
    })
    p.save()

    assert Preset.select().count() == 1

    data = {
        'id': 1,
        'name': 'p1-updated',
        'voices': {
            'melody': [
                {
                    'soundfont': 'test',
                    'bank': 1,
                    'program': 0,
                    'note': 12,
                    'polyphonic': True,
                    'muted': True,
                    'capo': 12,
                    'volume': 20,
                    'panning': 0,
                    'mode': 'midigurdy',
                    'finetune': 0,
                    'chien_threshold': 50,
                },
                {
                    'soundfont': 'test',
                    'bank': 1,
                    'program': 1,
                    'note': 1,
                    'polyphonic': False,
                    'muted': True,
                    'capo': 6,
                    'volume': 100,
                    'panning': 0,
                    'mode': 'midigurdy',
                    'finetune': 0,
                    'chien_threshold': 50,
                }
            ],
            'drone': [],
            'trompette': [],
        },
    }

    rv = client.put('/api/presets/1', data=json.dumps(data),
                    content_type='application/json')

    expected = data
    expected['number'] = 1

    assert rjson(rv) == expected
    assert rv.status_code == 200
    assert Preset.select().count() == 1


def test_get_nonexistant_preset_returns_404(client):
    rv = client.get('/api/presets/42')
    assert rv.status_code == 404


def test_put_nonexistant_preset_returns_404(client):
    data = {'id': 1, 'blafoo': 'test'}
    rv = client.put('/api/presets/42', data=json.dumps(data))
    assert rv.status_code == 404
