import pytest

from mg.mglib.api import MGCore


@pytest.fixture
def mg():
    return MGCore()


@pytest.mark.skip
def test_start_stop(mg):
    assert mg.started is False
    mg.start(None)
    assert mg.started is True
    mg.stop()
    assert mg.started is False


@pytest.mark.parametrize('name', [
    'pressure_to_poly',
    'pressure_to_pitch',
    'speed_to_melody_volume',
    'speed_to_drone_volume',
    'speed_to_trompette_volume',
    'speed_to_chien',
    'speed_to_percussion',
    'keyvel_to_notevel',
    'keyvel_to_tangent',
    'keyvel_to_keynoise',
    'chien_threshold_to_range',
])
def test_set_get_and_reset_ranges(mg, name):
    default = mg.get_mapping_ranges(name)
    assert len(default) > 0

    ranges = [{'src': 0, 'dst': 0}, {'src': 1, 'dst': 10}, {'src': 2, 'dst': 20}]
    mg.set_mapping_ranges(name, ranges)

    result = mg.get_mapping_ranges(name)
    assert result == ranges

    mg.reset_mapping_ranges(name)

    result = mg.get_mapping_ranges(name)
    assert result == default


def test_invalid_mapping_name_raises_exception(mg):
    with pytest.raises(Exception):
        mg.get_mapping_ranges('blafoo')

    with pytest.raises(Exception):
        mg.set_mapping_ranges('blafoo')


@pytest.mark.parametrize('name', [
    'melody1', 'melody2', 'melody3',
    'trompette1', 'trompette2', 'trompette3',
    'drone1', 'drone2', 'drone3',
])
def test_mute_string(mg, name):
    mg.mute_string(name, False)
    mg.mute_string(name, True)
