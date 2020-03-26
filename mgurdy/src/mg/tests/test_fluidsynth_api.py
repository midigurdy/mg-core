import os

import pytest

from mg.fluidsynth.api import FluidSynth, FluidSynthError
from mg.tests.conf import settings


@pytest.fixture(scope='module')
def fs(tmpdir_factory):
    output = tmpdir_factory.mktemp('fluidsynth').join('output.wav')
    print(settings.sound_dir)
    api = FluidSynth(soundfont_dir=settings.sound_dir, config={
        'audio.driver': 'file',
        'audio.file.name': str(output)
    })
    api.start()
    return api


def test_configure(fs):
    with pytest.raises(FluidSynthError):
        fs.configure({'bla': 'fasel'})

    with pytest.raises(ValueError):
        fs.configure({'synth.midi-channels': 'invalid'})

    fs.configure({
        'synth.midi-channels': 16,  # int param
        'synth.sample-rate': 11000.5,  # float param
        'synth.midi-bank-select': 'gm',  # string param
    })


def test_select_sound(fs):
    fs.set_channel_sound(0, 'mg.sf2', 0, 0)
    assert fs.get_loaded_fonts() == {'mg.sf2': 1}

    fs.set_channel_sound(1, 'mg.sf2', 0, 1)
    assert fs.get_loaded_fonts() == {'mg.sf2': 2}

    fs.set_channel_sound(0, 'test.sf2', 13, 37)
    assert fs.get_loaded_fonts() == {'test.sf2': 1, 'mg.sf2': 1}

    fs.set_channel_sound(1, 'test.sf2', 13, 37)
    assert fs.get_loaded_fonts() == {'mg.sf2': 0, 'test.sf2': 2}


def test_select_sound_with_missing_file_raises_error(fs):
    with pytest.raises(FluidSynthError):
        fs.set_channel_sound(0, 'blafoo.sf2', 0, 0)


def test_set_reverb(fs):
    fs.set_reverb(roomsize=0.5, damping=0.4, width=0.3, level=0.2)
    fs.set_reverb(roomsize=1, damping=2, width=3, level=4)


def test_set_channel_volume(fs):
    fs.set_channel_volume(0, 127)
    fs.set_channel_volume(15, 127)

    with pytest.raises(FluidSynthError):
        fs.set_channel_volume(1, 300)

    with pytest.raises(FluidSynthError):
        fs.set_channel_volume(16, 127)


def test_set_pitch_bend_range(fs):
    fs.set_pitch_bend_range(0, 5)


def test_get_cpu_load(fs):
    load = fs.get_cpu_load()
    assert load > 0
