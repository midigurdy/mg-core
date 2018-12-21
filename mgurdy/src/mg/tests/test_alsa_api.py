import selectors
import pytest

from mg.alsa.api import RawMIDI


@pytest.fixture
def rawmidi():
    return RawMIDI()


def test_get_rawmidi_ports(rawmidi):
    ports = rawmidi.get_ports()
    p = ports[0]
    print('Opening', p)
    p.open('r')
    print('Fileno is', p.fileno())
    print('Reading 3 bytes')
    print(p.read(6))
    print('Closing', p)
    p.close()
    p.open('r')
    p.close()
