import json
import pytest

from mg.tests.conf import settings
from mg.db import initialize
from mg.server.app import app as flask_app
from mg.state import State
from mg.mglib.api import MAPPINGS
from mg.mglib import mgcore


@pytest.fixture
def db():
    initialize(':memory:')


@pytest.fixture
def client(db):
    flask_app.config['state'] = State(settings)
    return flask_app.test_client()


def rjson(response):
    return json.loads(response.data.decode('utf8'))


def test_invalid_mapping(client):
    rv = client.get('/api/mappings/blafoo')
    assert rv.status_code == 404


def test_get_mapping(client):
    rv = client.get('/api/mappings/keyvel_to_notevel')
    assert rv.status_code == 200


def test_list_mappings(client):
    rv = client.get('/api/mappings')
    data = rjson(rv)
    assert rv.status_code == 200
    assert len(data) == len(MAPPINGS.keys())


def test_reset_mapping_to_factory_default(client):
    rv = client.delete('/api/mappings/keyvel_to_notevel')
    assert rv.status_code == 200


@pytest.mark.parametrize('name', MAPPINGS.keys())
@pytest.mark.parametrize('length', [1, 10, 20])
def test_update_mapping(client, name, length):
    ranges = [{'src': i, 'dst': i} for i in range(length)]
    rv = client.put('/api/mappings/{}'.format(name),
                    data=json.dumps({'ranges': ranges}),
                    content_type='application/json')
    data = rjson(rv)
    assert data.get('errors') is None
    assert rv.status_code == 200
    assert mgcore.get_mapping_ranges(name) == ranges


@pytest.mark.parametrize('invalid_ranges', [
    [],
    [{'src': 100, 'dst': 0}, {'src': 1, 'dst': 42}],
    [{'src': i, 'dst': i} for i in range(21)],
])
def test_invalid_ranges(client, invalid_ranges):
    mgcore.reset_mapping_ranges('keyvel_to_notevel')

    rv = client.put('/api/mappings/keyvel_to_notevel',
                    data=json.dumps({'ranges': invalid_ranges}),
                    content_type='application/json')
    data = rjson(rv)
    assert data.get('errors'), 'No errors returned!'
    assert rv.status_code == 400
    assert mgcore.get_mapping_ranges('keyvel_to_notevel') != invalid_ranges
