from enum import Enum
import logging

from .events import Event
from .device import InputDevice

LOG = logging.getLogger('input')


BUFFER_SIZE = 128


class MessageType(Enum):
    note_off = 0
    note_on = 1
    aftertouch = 2
    control_change = 3
    program_change = 4
    channel_pressure = 5
    pitch_bend = 6


class MidiMessage:
    """
    Very simple representation of a MIDI message. Only useful for channel
    messages, system common messages are not supported.
    """

    def __init__(self, channel, name, arg1=None, arg2=None):
        self.channel = channel
        self.name = name
        self.arg1 = arg1
        self.arg2 = arg2

    def __repr__(self):
        return '<MidiMessage: {} {} {} {}>'.format(
            self.channel, self.name, self.arg1, self.arg2)

    def to_binary(self):
        """
        Encode this message as binary array. Only used for testing purposes.
        """
        code = MessageType[self.name].value
        out = bytearray()
        out.append(0x80 | code << 4 | self.channel)
        out.append(self.arg1)
        # program_change and channel_pressure only have one data byte
        if code not in (4, 5):
            out.append(self.arg2 or 0)
        return out


class MidiInputEvent:
    def __init__(self, name=None, event=None, channel=None, arg1=None, arg2=None, cond=None):
        self.name = name
        self.channel = channel
        self.arg1 = arg1
        self.arg2 = arg2
        self.input_cond = self.parse_input_cond(cond) if cond else None
        self.event_expr = self.parse_event_expr(event.pop('expr')) if 'expr' in event else None
        self.event = event

    def parse_input_cond(self, code):
        try:
            return eval('lambda midi: {}'.format(code), None, None)
        except:
            LOG.exception('Error in input condition')
            return None

    def parse_event_expr(self, event_expr):
        try:
            expressions = {}
            for key, code in event_expr.items():
                expr = eval('lambda midi: {}'.format(code), None, None)
                expressions[key] = expr
            return expressions
        except:
            LOG.exception('Error in event expression')
            return None

    def matches_input(self, inp):
        if self.name is not None and inp.name != self.name:
            return False
        if self.channel is not None and inp.channel != self.channel:
            return False
        if self.arg1 is not None and inp.arg1 != self.arg1:
            return False
        if self.arg2 is not None and inp.arg2 != self.arg2:
            return False
        if self.input_cond is not None and not self.input_cond(inp):
            return False
        return True

    def create_event(self, inp):
        event = dict(self.event)
        if self.event_expr:
            for key, expr in self.event_expr.items():
                event[key] = expr(inp)
        return Event.from_mapping(event)


class MidiInput(InputDevice):
    def __init__(self, port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = port
        self.parser = MidiParser()
        self.mappings = []

    @classmethod
    def from_config(cls, config, port):
        inp = MidiInput(
            port,
            name=config['device'],
            filename=config['device'],
            debug=bool(config.get('debug')))
        inp.set_mappings(config['mappings'])
        return inp

    def open(self):
        self.port.open()
        self.fd = self.port.fileno()
        return self.fd

    def close(self):
        self.port.close()

    def set_mappings(self, mappings):
        self.mappings = []

        for m in mappings:
            self.mappings.append(MidiInputEvent(**m['input'], event=m['event']))

    def map(self, val):
        event = self.get_matching_event(val)
        return event

    def get_matching_event(self, val):
        for ie in self.mappings:
            if ie.matches_input(val):
                return ie.create_event(val)

    def read(self):
        messages = []
        while True:
            data = self.port.read(BUFFER_SIZE)
            if not data:
                break
            messages.extend(self.parser.parse(data))
        return messages


class MidiParser:
    """
    Very simple parser for raw MIDI data streams. Only returns channel messages
    and ignores everything else it can't understand.
    """

    def __init__(self):
        self.code = None
        self.channel = None
        self.arg1 = None

    def parse(self, data):
        """
        Parse the bytes and return a list of understood messages. The parser
        is stateful and will also handle partial (split) messages supplied via
        consecutive calls to this function.
        """
        messages = []

        for byte in data:
            if byte & 0x80:  # status byte
                code = (byte >> 4) & 0x7
                if code > 6:
                    continue
                self.code = code
                self.channel = byte & 0xF
                self.arg1 = None
            else:
                if self.code is None:
                    continue
                elif self.code in (4, 5):
                    self.arg1 = byte
                    messages.append(self._create_msg(None))
                elif self.arg1 is not None:
                    messages.append(self._create_msg(byte))
                else:
                    self.arg1 = byte
        return messages

    def _create_msg(self, arg2=None):
        if arg2 is None:
            msg = MidiMessage(self.channel, MessageType(self.code).name, self.arg1)
        else:
            msg = MidiMessage(self.channel, MessageType(self.code).name,
                              self.arg1, arg2)
        self.channel = None
        self.code = None
        self.arg1 = None
        return msg
