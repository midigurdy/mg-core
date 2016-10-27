import os
import shutil
import json
import pytest

from mg.server.app import app as flask_app
from mg.conf import settings
from mg.state import State


def get_testdata_dir():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, '../data')


@pytest.fixture
def client():
    flask_app.config['state'] = State()
    return flask_app.test_client()


@pytest.fixture
def testdata_dir():
    settings.sound_dir = get_testdata_dir()
    return settings.data_dir


@pytest.fixture
def tmpdata_dir(tmpdir):
    settings.sound_dir = str(tmpdir)
    settings.upload_dir = str(tmpdir)
    return tmpdir


def rjson(response):
    return json.loads(response.data.decode('utf8'))


def test_list_empty_soundfonts(client, tmpdata_dir):
    rv = client.get('/api/sounds')

    assert rv.status_code == 200
    assert rjson(rv) == []


def test_list_soundfonts(client, testdata_dir):
    rv = client.get('/api/sounds')

    assert rv.status_code == 200
    assert len(rjson(rv)) == 2


def test_get_soundfont(client, testdata_dir):
    rv = client.get('/api/sounds/mg.sf2')

    expected = MG_SOUNDFONT

    assert rv.status_code == 200
    assert rjson(rv) == expected


def test_upload_soundfont(client, tmpdata_dir):
    filename = os.path.join(get_testdata_dir(), 'mg.sf2')
    sfile = open(filename, 'rb')

    rv = client.post('/api/upload/sound/test.sf2', data=sfile)

    expected = {
        'author': 'Marcus Weseloh',
        'copyright': 'Marcus Weseloh 2017',
        'creation_date': '01.01.2017',
        'description': 'This is a MidiGurdy Test SoundFont',
        'filename': 'test.sf2',
        'filesize': 1286,
        'id': 'test.sf2',
        'mode': 'midigurdy',
        'name': 'MidiGurdy Test Font',
        'sounds': [
            {'bank': 0,
             'note': 60,
             'id': 'test.sf2:0:0',
             'name': 'First Melody',
             'program': 0,
             'type': 'melody'},
            {'bank': 0,
             'note': -1,
             'id': 'test.sf2:0:1',
             'name': 'Second Melody',
             'program': 1,
             'type': 'melody'},
            {'bank': 1,
             'note': 50,
             'id': 'test.sf2:1:0',
             'name': 'First Drone',
             'program': 0,
             'type': 'drone'},
            {'bank': 1,
             'note': -1,
             'id': 'test.sf2:1:1',
             'name': 'Second Drone',
             'program': 1,
             'type': 'drone'},
            {'bank': 2,
             'note': -1,
             'id': 'test.sf2:2:0',
             'name': 'First Trompette',
             'program': 0,
             'type': 'trompette'},
            {'bank': 2,
             'note': -1,
             'id': 'test.sf2:2:1',
             'name': 'Second Trompette',
             'program': 1,
             'type': 'trompette'},
            {'bank': 3,
             'note': -1,
             'id': 'test.sf2:3:0',
             'name': 'Keynoise',
             'program': 0,
             'type': 'keynoise'},
            {'bank': 10,
             'note': -1,
             'id': 'test.sf2:10:0',
             'name': 'Generic Sound',
             'program': 0,
             'type': 'generic'}
        ],
        'tool': 'Polyphone',
    }

    assert rv.status_code == 200
    assert rjson(rv) == expected


def test_upload_with_existing_soundfont(client, tmpdata_dir):
    filename = os.path.join(get_testdata_dir(), 'mg.sf2')
    assert not os.path.exists(os.path.join(tmpdata_dir, 'test.sf2'))

    # create soundfont
    rv = client.post('/api/upload/sound/test.sf2', data=open(filename, 'rb'))
    assert rv.status_code == 200
    assert os.path.exists(os.path.join(tmpdata_dir, 'test.sf2'))

    # now try to upload again
    rv = client.post('/api/upload/sound/test.sf2', data=open(filename, 'rb'))
    assert rv.status_code == 200


def test_delete_soundfont(client, tmpdata_dir):
    shutil.copy(os.path.join(get_testdata_dir(), 'mg.sf2'), str(tmpdata_dir))
    assert os.path.isfile(os.path.join(tmpdata_dir, 'mg.sf2'))

    rv = client.delete('/api/sounds/mg.sf2')

    assert not rv.data
    assert rv.status_code == 204
    assert not os.path.isfile(os.path.join(tmpdata_dir, 'mg.sf2'))


def test_download_soundfont(client, testdata_dir):
    rv = client.get('/download/sounds/test.sf2')
    assert rv.status_code == 200


def test_upload_invalid_soundfont_returns_error(client, tmpdata_dir):
    invalid_sf2 = tmpdata_dir.join('invalid.sf2')
    invalid_sf2.write(1234)

    # create with invalid file name
    rv = client.post('/api/upload/sound/test.blafoo', data=open(str(invalid_sf2), 'rb'))

    assert rjson(rv) == {'message': 'Invalid file extension, please use .sf2 or .sf3 files'}
    assert rv.status_code == 400

    # create with file
    rv = client.post('/api/upload/sound/test.sf2', data=open(str(invalid_sf2), 'rb'))

    assert rjson(rv) == {'message': 'Invalid file format, is this really a SoundFont?'}
    assert rv.status_code == 400


MG_SOUNDFONT = {
    'author': 'Marcus Weseloh',
    'copyright': 'Marcus Weseloh 2017',
    'creation_date': '01.01.2017',
    'description': 'This is a MidiGurdy Test SoundFont',
    'filename': 'mg.sf2',
    'filesize': 1286,
    'id': 'mg.sf2',
    'mode': 'midigurdy',
    'name': 'MidiGurdy Test Font',
    'sounds': [
        {'bank': 0,
         'note': 60,
         'id': 'mg.sf2:0:0',
         'name': 'First Melody',
         'program': 0,
         'type': 'melody'},
        {'bank': 0,
         'note': -1,
         'id': 'mg.sf2:0:1',
         'name': 'Second Melody',
         'program': 1,
         'type': 'melody'},
        {'bank': 1,
         'note': 50,
         'id': 'mg.sf2:1:0',
         'name': 'First Drone',
         'program': 0,
         'type': 'drone'},
        {'bank': 1,
         'note': -1,
         'id': 'mg.sf2:1:1',
         'name': 'Second Drone',
         'program': 1,
         'type': 'drone'},
        {'bank': 2,
         'note': -1,
         'id': 'mg.sf2:2:0',
         'name': 'First Trompette',
         'program': 0,
         'type': 'trompette'},
        {'bank': 2,
         'note': -1,
         'id': 'mg.sf2:2:1',
         'name': 'Second Trompette',
         'program': 1,
         'type': 'trompette'},
        {'bank': 3,
         'note': -1,
         'id': 'mg.sf2:3:0',
         'name': 'Keynoise',
         'program': 0,
         'type': 'keynoise'},
        {'bank': 10,
         'note': -1,
         'id': 'mg.sf2:10:0',
         'name': 'Generic Sound',
         'program': 0,
         'type': 'generic'}
    ],
    'tool': 'Polyphone',
}
