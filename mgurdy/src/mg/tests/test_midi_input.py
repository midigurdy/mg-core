from queue import Queue

import pytest

from mg.input.events import Key, Action
from mg.input.manager import InputManager
from mg.input.midi import MidiInput, MidiMessage
from mg.alsa.api import RawMIDIPort


class MockedRawMIDIPort(RawMIDIPort):
    def __init__(self, _filename, *args, **kwargs):
        self._filename = _filename
        self._fd = None
        super().__init__(*args, **kwargs)

    def open(self, nonblock=True):
        self._fd = open(self._filename, 'rb')
        return self

    def close(self):
        self._fd.close()

    def read(self, size):
        return self._fd.read(size)

    def fileno(self):
        return self._fd.fileno()


class MockedMidiInput(MidiInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = MockedRawMIDIPort(self.filename, 1, 1, 1,
                                      'mocked_card', 'mocked_subdevice')


@pytest.fixture
def port(tmpdir):
    tmpfile = tmpdir.join('testinput').ensure()
    return MockedRawMIDIPort(str(tmpfile), 1, 1, 1,
                             'mocked_card', 'mocked_subdevice')


@pytest.fixture
def midi(port):
    return MidiInput(port, port._filename)


def test_read_empty(midi):
    midi.open()

    assert midi.read() == []

    midi.close()


def test_read_channel_messages(midi):
    midi.open()

    msg1 = MidiMessage(1, 'note_on', 60, 127)
    msg2 = MidiMessage(2, 'program_change', 126)
    msg3 = MidiMessage(3, 'note_off', 61, 1)

    with open(midi.filename, 'wb') as f:
        f.write(msg1.to_binary())
        f.write(msg2.to_binary())
        f.write(msg3.to_binary())

    result = midi.read()

    assert len(result) == 3

    m1, m2, m3 = result

    assert m1.name == 'note_on'
    assert m1.arg1 == 60
    assert m1.arg2 == 127

    assert m2.name == 'program_change'
    assert m2.arg1 == 126
    assert m2.arg2 is None

    assert m3.name == 'note_off'
    assert m3.arg1 == 61
    assert m3.arg2 == 1


def test_ignore_bogus_data(midi):
    midi.open()

    with open(midi.filename, 'wb') as f:
        f.write(bytes([1, 2, 3, 4, 5, 6, 7, 9]))

    assert midi.read() == []


def test_ignore_sysex_data(midi):
    midi.open()

    with open(midi.filename, 'wb') as f:
        f.write(b'0x70')  # sysex start
        f.write(bytes([42] * 1011))  # some sysex payload
        f.write(b'0x7F')  # sysex end

    assert midi.read() == []


def test_realtime_messages(midi):
    midi.open()

    msg = MidiMessage(0, 'note_on', 60, 127)
    msgdata = msg.to_binary()

    with open(midi.filename, 'wb') as f:
        f.write(msgdata[:1])  # start note on message
        f.write(bytes(0xF8 + i for i in range(8)))  # all possible realtime msgs
        f.write(msgdata[1:])  # rest of note on message

    result = midi.read()

    assert len(result) == 1
    assert result[0].name == 'note_on'
    assert result[0].arg1 == 60
    assert result[0].arg2 == 127


def test_poll_device_without_config_returns_no_events(midi):
    queue = Queue()
    manager = InputManager(queue)
    manager.register(midi)

    with open(midi.filename, 'wb') as f:
        f.write(MidiMessage(0, 'note_on', 60, 127).to_binary())

    manager.poll()
    assert queue.qsize() == 0


def test_simple_map_two_byte_messages(port):
    config = {
        'name': 'Test Map',
        'type': 'midi',
        'device': port._filename,
        'mappings': [
            {
                'input': {
                    'channel': 1,
                    'name': 'note_on',
                    'arg1': 60,
                    'arg2': 127,
                },
                'event': {
                    'type': 'input',
                    'name': 'fn1',
                    'action': 'up'
                },
            },
            {
                'input': {
                    'channel': 2,
                    'name': 'note_on',
                    'arg1': 60,
                    'arg2': 127,
                },
                'event': {
                    'type': 'input',
                    'name': 'fn2',
                    'action': 'up'
                },
            },
        ],
    }

    queue = Queue()
    manager = InputManager(queue)
    inp = MidiInput.from_config(config, port=port)
    manager.register(inp)

    with open(port._filename, 'wb') as f:
        # should all be ignored
        f.write(MidiMessage(7, 'note_on', 60, 127).to_binary())
        f.write(MidiMessage(1, 'note_off', 60, 127).to_binary())
        f.write(MidiMessage(1, 'note_on', 1, 127).to_binary())
        f.write(MidiMessage(1, 'note_on', 60, 1).to_binary())

        # only these should be picked up
        f.write(MidiMessage(1, 'note_on', 60, 127).to_binary())
        f.write(MidiMessage(2, 'note_on', 60, 127).to_binary())

    manager.poll()

    assert queue.qsize() == 2

    e = queue.get_nowait()
    assert e.name == Key.fn1
    assert e.action == Action.up

    e = queue.get_nowait()

    assert e.name == Key.fn2
    assert e.action == Action.up


def test_simple_map_single_byte_messages(port):
    config = {
        'name': 'Test Map',
        'type': 'midi',
        'device': port._filename,
        'mappings': [
            {
                'input': {
                    'channel': 1,
                    'name': 'program_change',
                    'arg1': 60,
                },
                'event': {
                    'type': 'input',
                    'name': 'fn1',
                    'action': 'up'
                },
            },
        ],
    }

    queue = Queue()
    manager = InputManager(queue)
    inp = MidiInput.from_config(config, port=port)
    manager.register(inp)

    with open(port._filename, 'wb') as f:
        f.write(MidiMessage(1, 'program_change', 60).to_binary())

    manager.poll()

    assert queue.qsize() == 1

    e = queue.get_nowait()
    assert e.name == Key.fn1
    assert e.action == Action.up


def test_wildcard_match(port):
    config = {
        'name': 'Test Map',
        'type': 'midi',
        'debug': True,
        'device': port._filename,
        'mappings': [
            {
                'input': {
                    'channel': 1,
                    'name': 'note_on',
                },
                'event': {
                    'type': 'input',
                    'name': 'fn1',
                    'action': 'up',
                },
            },
            # catch-all!
            {
                'input': {
                },
                'event': {
                    'type': 'input',
                    'name': 'fn2',
                    'action': 'down',
                },
            },
        ],
    }

    queue = Queue()
    manager = InputManager(queue)
    inp = MidiInput.from_config(config, port=port)
    manager.register(inp)

    with open(port._filename, 'wb') as f:
        f.write(MidiMessage(1, 'note_on', 7, 42).to_binary())
        f.write(MidiMessage(3, 'program_change', 7).to_binary())
        f.write(MidiMessage(5, 'control_change', 7, 42).to_binary())

    manager.poll()

    assert queue.qsize() == 3

    e = queue.get_nowait()
    assert e.name == Key.fn1
    assert e.action == Action.up

    e = queue.get_nowait()
    assert e.name == Key.fn2
    assert e.action == Action.down

    e = queue.get_nowait()
    assert e.name == Key.fn2
    assert e.action == Action.down
