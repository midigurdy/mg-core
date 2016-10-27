from queue import Queue

import pytest

from mg.input.evdev import EvDevInput, EvDevEvent
from mg.input.events import Key, Action
from mg.input.manager import InputManager


@pytest.fixture
def dev(tmpdir):
    tmpfile = tmpdir.join('testinput').ensure()
    return str(tmpfile)


def test_read_empty(dev):
    evdev = EvDevInput(dev)
    evdev.open()

    assert evdev.read() == []

    evdev.close()


def test_read_single_event(dev):
    evdev = EvDevInput(dev)
    event = EvDevEvent(1, 2, 3, 4, 5)
    evdev.open()

    with open(dev, 'wb') as f:
        f.write(event.to_binary())

    assert evdev.read() == [event]

    evdev.close()


def test_read_multiple_events(dev):
    evdev = EvDevInput(dev)
    evdev.open()
    events = [EvDevEvent(i, i, i, i, i) for i in range(50)]

    with open(dev, 'wb') as f:
        for event in events:
            f.write(event.to_binary())

    assert evdev.read() == events

    evdev.close()


def test_read_evdev_binary_event_format():
    raw = bytes.fromhex(
        '10 3a e6 58 00 00 00 00 '  # secs
        '80 91 0d 00 00 00 00 00 '  # usecs
        '01 00 '                    # type
        '10 01 '                    # code
        '01 00 09 00')              # value
    ev = EvDevEvent.from_binary(raw)

    assert ev.secs == 1491483152
    assert ev.usecs == 889216
    assert ev.type == 1
    assert ev.code == 272
    assert ev.value == 589825

    assert ev.to_binary() == raw


@pytest.mark.timeout(1)
def test_poll_without_handlers_should_return_immediately():
    manager = InputManager(Queue())
    manager.poll()


def test_poll_device_without_config_returns_no_event(dev):
    queue = Queue()
    manager = InputManager(queue)
    manager.register(EvDevInput(dev))
    event = EvDevEvent(1, 2, 3, 4, 5)
    with open(dev, 'wb') as f:
        f.write(event.to_binary())

    manager.poll()
    assert queue.qsize() == 0


def test_create_from_config(dev):
    config = [{
        'name': 'Test Map',
        'type': 'evdev',
        'debug': True,
        'device': dev,
        'mappings': [
            {
                'input': {
                    'type': 1,
                    'code': 44,
                    'value': 1
                },
                'event': {
                    'type': 'input',
                    'name': 'fn1',
                    'action': 'up'
                },
            },
            {
                'input': {
                    'type': 1,
                    'code': 44,
                    'value': 0
                },
                'event': {
                    'type': 'input',
                    'name': 'fn1',
                    'action': 'down'
                },
            },
            {
                'input': {
                    'type': 1,
                    'code': 45,
                    'value': 1
                },
                'event': {
                    'type': 'input',
                    'name': 'fn2',
                    'action': 'up'
                },
            },
            {
                'input': {
                    'type': 1,
                    'code': 45,
                    'value': 0
                },
                'event': {
                    'type': 'input',
                    'name': 'fn2',
                    'action': 'down'
                },
            },
            {
                'input': {
                    'type': 2,
                    'code': 0,
                    'value': -1,
                },
                'event': {
                    'type': 'input',
                    'name': 'encoder',
                    'action': 'up',
                    'value': -1,
                },
            },
            {
                'input': {
                    'type': 2,
                    'code': 0,
                    'value': 1,
                },
                'event': {
                    'type': 'input',
                    'name': 'encoder',
                    'action': 'down',
                    'value': 1,
                },
            },
        ],
    }]

    queue = Queue()
    manager = InputManager(queue)
    manager.set_config(config)

    with open(dev, 'wb') as f:
        e = EvDevEvent(1, 1, 1, 44, 0)
        f.write(e.to_binary())

        e = EvDevEvent(1, 1, 1, 45, 1)
        f.write(e.to_binary())

        e = EvDevEvent(1, 1, 2, 0, -1)
        f.write(e.to_binary())

        e = EvDevEvent(1, 1, 2, 0, 1)
        f.write(e.to_binary())

    manager.poll()

    e1 = queue.get_nowait()
    assert e1.name == Key.fn1
    assert e1.action == Action.down

    e2 = queue.get_nowait()
    assert e2.name == Key.fn2
    assert e2.action == Action.up

    e3 = queue.get_nowait()
    assert e3.name == Key.encoder
    assert e3.action == Action.up
    assert e3.value == -1

    e4 = queue.get_nowait()
    assert e4.name == Key.encoder
    assert e4.action == Action.down
    assert e4.value == 1
