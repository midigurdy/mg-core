import pytest

from mg.fluidsynth.api import FluidSynth
from mg.state import State
from mg.controller import SynthController


@pytest.fixture
def ctrl():
    fluid = FluidSynth()
    fluid.configure({
        "audio.driver": "file",
        "synth.ladspa.active": 1,
        "synth.dynamic-sample-loading": 1,
    })
    fluid.start()

    fluid.ladspa.add_effect('sympa', '../../mg-effects/build/sympathetic.so', mix=True)
    fluid.ladspa.link_effect('sympa', 'Input', 'Reverb:Send')
    fluid.ladspa.link_effect('sympa', 'Output Left', 'Main:L')
    fluid.ladspa.link_effect('sympa', 'Output Right', 'Main:R')
    fluid.ladspa.activate()

    yield SynthController(fluid, State())

    fluid.stop()


# FIXME: to be continued!
@pytest.mark.parametrize('name,kwargs', [
    ('synth_gain_changed', {'gain': 50}),
    ('active_preset_voice_muted_changed', {}),
    ('active_preset_voice_capo_changed', {}),
    ('fine_tune_changed', {}),
    ('coarse_tune_changed', {}),
    ('multi_chien_threshold_changed', {}),
    ('active_preset_changed', {}),
])
def test_synth_gain_changed(ctrl, name, kwargs):
    method = getattr(ctrl, name)
    method(**kwargs)
