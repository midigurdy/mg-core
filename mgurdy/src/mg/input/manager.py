import time
import json
import selectors
import logging
import threading
import prctl

from mg.exceptions import InvalidInputMapError

from .evdev import EvDevInput
from .midi import MidiInput

LOG = logging.getLogger()


class InputManager(threading.Thread):
    def __init__(self, queue):
        super().__init__(name='mg-input-handler')
        self.daemon = True

        self.selector = selectors.PollSelector()
        self.inputs = {}
        self.queue = queue
        self.initial_events = []

    def register(self, inp):
        self.selector.register(inp.open(), selectors.EVENT_READ, inp)
        if inp.filename in self.inputs:
            LOG.error('Handler for "%s" already registered!' % inp.filename)
            return
        self.inputs[inp.filename] = inp
        self.initial_events.extend(inp.get_initial_events() or [])

    def unregister(self, filename):
        inp = self.inputs.get(filename)
        if inp is None:
            LOG.warn('No handler registered for input "%s"' % filename)
            return
        self.selector.unregister(inp.fd)
        del self.inputs[filename]

    def load_config(self, filename):
        with open(filename, 'r') as f:
            config = json.load(f)
        self.set_config(config)

    def clear(self):
        while self.inputs:
            self.unregister(self.inputs[0])

    def set_config(self, config):
        self.clear()

        input_classes = {
            'evdev': EvDevInput,
            'midi': MidiInput,
        }

        for entry in config:
            try:
                klass = input_classes[entry['type']]
                inp = klass.from_config(entry)
                self.register(inp)
            except Exception as e:
                raise InvalidInputMapError('Error in input map "{}": {}'.format(
                    entry.get('name', 'UNNAMED'), e))

    def run(self):
        prctl.set_name(self.name)
        try:
            for event in self.initial_events:
                self.queue.put(event)
            self.initial_events = []
        except Exception:
            LOG.exception('Error while handling initial events')
        while True:
            try:
                if not self.poll():
                    time.sleep(.5)  # to prevent busy looping on empty selector
            except Exception:
                LOG.exception('Error while polling inputs')

    def poll(self):
        if not self.inputs:
            return False
        for key, mask in self.selector.select(timeout=1):
            inp = key.data
            while True:
                try:
                    result = inp.read()
                except OSError as e:
                    if e.errno == 19:  # ENODEV
                        self.unregister(inp.filename)
                    raise e
                if not result:
                    break
                for entry in result:
                    event = inp.map(entry)
                    if event:
                        print('inp', inp, event)
                        self.queue.put(event)
                    elif inp.debug:
                        LOG.debug('Missing mapping in %s for %s' % (
                            inp.name, entry))
        return True
