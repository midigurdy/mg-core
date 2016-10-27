import os
import stat
import logging

from .events import MdevEvent
from .device import InputDevice


BUFSIZE = 10000
LOG = logging.getLogger('input')


class MdevInput(InputDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mappings = {}
        self.initial_events = []

    def set_mappings(self, mappings):
        pass

    def get_initial_events(self):
        events = self.initial_events
        self.initial_events = None
        return events

    def open(self):
        if not self._is_fifo():
            self._read_initial_events()
        self._create_fifo()
        self.fd = os.open(self.filename, os.O_RDWR | os.O_NONBLOCK)
        return self.fd

    def map(self, val):
        toks = val.split()
        if len(toks) != 4:
            LOG.error('Invalid mdev event line: %s' % val)
            return
        return MdevEvent(*toks)

    def read(self):
        lines = []
        while True:
            try:
                raw = os.read(self.fd, 100000)
            except BlockingIOError:
                break
            lines.extend([line for line in raw.decode().split('\n') if line])
        return lines

    def _read_initial_events(self):
        try:
            with open(self.filename, 'r') as f:
                data = f.read()
            lines = [l for l in data.split('\n') if l]
            self.initial_events = []
            for line in lines:
                event = self.map(line)
                if event is not None:
                    self.initial_events.append(event)
        except Exception as e:
            LOG.exception('Unable to read initial events')

    def _create_fifo(self):
        for attempt in range(10):
            try:
                if os.path.isfile(self.filename):
                    os.unlink(self.filename)
                if not self._is_fifo():
                    os.mkfifo(self.filename)
            except Exception as e:
                if attempt > 0:
                    LOG.exception('Unable to create mdev fifo, trying again')
                    continue
                else:
                    raise RuntimeError('Failed to create mdev fifo, giving up')
            else:
                break

    def _is_fifo(self):
        try:
            if not os.path.exists(self.filename):
                return False
            return stat.S_ISFIFO(os.stat(self.filename).st_mode)
        except OSError as e:
            LOG.exception('Error while trying to check is file is fifo')
            return False
