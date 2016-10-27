from enum import Enum

from mg.exceptions import InvalidInputMapError


class Event:
    @classmethod
    def from_mapping(self, entry):
        entry = dict(entry)
        etype = entry.pop('type')
        if etype == 'input':
            klass = InputEvent
        elif etype == 'state':
            klass = StateEvent
        elif etype == 'state_change':
            klass = StateChangeEvent
        elif etype == 'state_action':
            klass = StateActionEvent
        else:
            raise InvalidInputMapError('Invalid event type "%s"' % etype)
        return klass(**entry)

    def set_variables(self, source):
        for name, val in self.__dict__.items():
            if isinstance(val, str) and val[0] == '$':
                if val.endswith('+1'):
                    val = int(getattr(source, val[1:-2])) + 1
                else:
                    val = getattr(source, val[1:])
                setattr(self, name, val)

    def __str__(self):
        return '<Event {}>'.format(self.__dict__)


class InputEvent(Event):
    type = 'input'

    def __init__(self, name, action, value=None):
        self.name = Key[name]
        self.action = Action[action]
        self.value = self.action.value if value is None else value

    def clone(self):
        return InputEvent(self.name.name, self.action.name, self.value)

    def down(self, key=None):
        return (key is None or self.name == key) and self.action == Action.down

    def up(self, key=None):
        return (key is None or self.name == key) and self.action == Action.up

    def pressed(self, key):
        return self.name == key and self.action in (Action.short, Action.long)

    def short_pressed(self, key):
        return self.name == key and self.action == Action.short

    def long_pressed(self, key):
        return self.name == key and self.action == Action.long


class StateEvent(Event):
    type = 'state'

    def __init__(self, name, data):
        self.name = name
        self.data = data

    def clone(self):
        return StateEvent(name=self.name, data=self.data)


class StateChangeEvent(Event):
    type = 'state_change'

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def clone(self):
        return StateChangeEvent(self.name, self.value)


class StateActionEvent(Event):
    type = 'state_action'

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def clone(self):
        return StateActionEvent(self.name, self.value)


class MdevEvent(Event):
    type = 'mdev'

    def __init__(self, action, source, subsystem, device):
        self.action = action
        self.source = source
        self.subsystem = subsystem
        self.device = device

    def clone(self):
        return MdevEvent(self.action, self.source, self.subsystem, self.device)


class Key(Enum):
    select = 1
    back = 2
    fn1 = 3
    fn2 = 4
    fn3 = 5
    fn4 = 6
    top1 = 7
    top2 = 8
    top3 = 9
    mod1 = 10
    mod2 = 11
    encoder = 12


class Action(Enum):
    up = 1
    down = 2
    pressed = 3
    short = 4
    long = 5
