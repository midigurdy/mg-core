from contextlib import contextmanager
import threading
import logging


log = logging.getLogger('signals')


class Signals:
    def __init__(self):
        self.handlers = {}
        self.propagate_exceptions = False
        self._threadlocal = threading.local()

    def set_client_id(self, id):
        self._threadlocal.client_id = id

    def get_client_id(self):
        return getattr(self._threadlocal, 'client_id', None)

    def register(self, event, handler):
        handlers = self.handlers.setdefault(event, [])
        handlers.append(handler)

    def unregister(self, event, handler):
        try:
            self.handlers[event].remove(handler)
        except ValueError:
            log.error('handler {} not registered for event {}!'.format(handler, event))
        except KeyError:
            log.error('event {} not registered for handler!'.format(event, handler))

    def emit(self, name, data=None):
        if data is None:
            data = {}
        cid = self.get_client_id()
        if cid:
            data['client_id'] = cid

        if getattr(self._threadlocal, 'suppressed', None):
            self._threadlocal.suppressed[-1].append((name, data))
            return

        handled = False

        for handler in self.handlers.get(name, []):
            try:
                handler(name, data)
                handled = True
                log.debug('%s (%s) (%s)', name, handler, data)
            except:
                log.exception('Error in handler for "{}" signal'.format(name))
                if self.propagate_exceptions:
                    raise
        for handler in self.handlers.get('__all__', []):
            try:
                handler(name, data)
                handled = True
                log.debug('%s (__all__ %s) (%s)', name, handler, data)
            except:
                log.exception('Error in handler for "__all__" signal')
                if self.propagate_exceptions:
                    raise
        if not handled:
            log.debug('IGNORED %s (%s)', name, data)

    @contextmanager
    def suppress(self):
        """
        Suppress all signals emitted in this context. Returns a list of
        (suppressed) signals emitted.
        """
        suppressed_signals = []
        if getattr(self._threadlocal, 'suppressed', None):
            self._threadlocal.suppressed.append(suppressed_signals)
        else:
            self._threadlocal.suppressed = [suppressed_signals]

        yield suppressed_signals

        self._threadlocal.suppressed.pop()


signals = Signals()


MISSING = '__MISSING__'


class EventEmitter:
    def __init__(self, prefix=None):
        self.prefix = prefix

    def __setattr__(self, name, value):
        prop = getattr(self.__class__, name, None)
        if isinstance(prop, property):
            if prop.fset is None:
                raise AttributeError('Attribute %s is read-only!' % name)
            prop.fset(self, value)
        else:
            if name.startswith('_'):
                super().__setattr__(name, value)
            else:
                if getattr(self, name, MISSING) != value:
                    self.__dict__[name] = value
                    self.notify('%s:changed' % name, {name: value})

    def notify(self, name, data=None):
        if self.prefix:
            name = ':'.join((self.prefix, name))
        if data is None:
            data = {}
        data['sender'] = self
        signals.emit(name, data)


class EventListener:
    events = []

    def handle_event(self, name, data):
        handler_name = name.replace(':', '_')
        handler = getattr(self, handler_name)
        handler(**data)

    def start_listening(self):
        for name in self.events:
            signals.register(name, self.handle_event)

    def stop_listening(self):
        for name in self.events:
            signals.unregister(name, self.handle_event)
