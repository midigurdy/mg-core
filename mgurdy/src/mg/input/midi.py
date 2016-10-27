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
    def __init__(self, name=None, event=None, channel=None, arg1=None, arg2=None,
                 condition=None, modifier=None):
        self.event = event
        self.name = name
        self.channel = channel
        self.arg1 = arg1
        self.arg2 = arg2
        self.condition = self.parse_condition_expr(condition) if condition else None
        self.modifier = self.parse_modifier_expr(modifier) if modifier else None

    def parse_condition_expr(self, expr):
        toks = expr.split()
        attr = toks[0]
        checker = getattr(self, '%s_condition' % toks[1])
        args = toks[2:]
        return lambda x: checker(getattr(x, attr), *args)

    def parse_modifier_expr(self, expr):
        toks = expr.split()
        attr = toks[0]
        if len(toks) > 1:
            modifier = getattr(self, '%s_modifier' % toks[1])
            args = toks[2:]
            return lambda x: modifier(getattr(x, attr), *args)
        else:
            return lambda x: getattr(x, attr)

    def midi_percent_modifier(self, val):
        val = int(val)
        if val < 0:
            val = 0
        if val > 127:
            val = 127
        return int(val / 127.0 * 100)

    def plus_modifier(self, val, arg):
        return int(val) + int(arg)

    def minus_modifier(self, val, arg):
        return int(val) - int(arg)

    def range_condition(self, val, start, end):
        val = int(val)
        return val >= int(start) and val <= int(end)

    def matches_input(self, inp):
        if self.name is not None and inp.name != self.name:
            return False
        if self.channel is not None and inp.channel != self.channel:
            return False
        if self.arg1 is not None and inp.arg1 != self.arg1:
            return False
        if self.arg2 is not None and inp.arg2 != self.arg2:
            return False
        if self.condition is not None and not self.condition(inp):
            return False
        return True

    def create_event(self, inp):
        event = Event.from_mapping(self.event)
        if self.modifier is not None:
            event.value = self.modifier(inp)
        return event


class MidiInput(InputDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = MidiParser()
        self.mappings = []

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
            data = self.fd.read(BUFFER_SIZE)
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
                elif self.code in (4, 5) or self.arg1 is not None:
                    messages.append(self._create_msg(byte))
                else:
                    self.arg1 = byte
        return messages

    def _create_msg(self, arg2=None):
        if self.arg1 is None:
            msg = MidiMessage(self.channel, MessageType(self.code).name, arg2)
        else:
            msg = MidiMessage(self.channel, MessageType(self.code).name,
                              self.arg1, arg2)
        self.channel = None
        self.code = None
        self.arg1 = None
        return msg
