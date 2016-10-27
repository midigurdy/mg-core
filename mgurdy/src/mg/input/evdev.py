import struct
import logging

from collections import namedtuple

from .events import Event
from .device import InputDevice

LOG = logging.getLogger('input')

EV_FORMAT = 'llHHi'
EV_SIZE = struct.calcsize(EV_FORMAT)
EV_STRUCT = struct.Struct(EV_FORMAT)


class EvDevEvent(namedtuple('EvDevEvent', 'secs, usecs, type, code, value')):
    def timestamp(self):
        return self.secs * 1000000 + self.usecs

    @classmethod
    def from_binary(cls, data):
        return cls._make(EV_STRUCT.unpack_from(data))

    def to_binary(self):
        """
        Only used for testing purposes
        """
        return EV_STRUCT.pack(*self)


class EvDevInput(InputDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mappings = {}

    def set_mappings(self, mappings):
        self.mappings = {}
        for m in mappings:
            i = m['input']

            event = Event.from_mapping(m['event'])

            code = (i['type'], i['code'], i['value'])
            if code in self.mappings:
                LOG.warning('Duplicate entry in %s map: %s' %
                            (self.name, code))
            self.mappings[code] = event

    def map(self, val):
        key = (val.type, val.code, val.value)
        event = self.mappings.get(key)
        if event:
            event = event.clone()
            event.ts = val.timestamp()
        return event

    def read(self):
        events = []
        while True:
            raw = self.fd.read(EV_SIZE)
            if not raw:
                break
            events.append(EvDevEvent.from_binary(raw))
        return events
