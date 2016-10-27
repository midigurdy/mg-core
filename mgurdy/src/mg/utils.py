from threading import Thread, Event, Timer
import logging
import time
import prctl

MIDI_NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def percent2midi(val):
    return round(scale(val, 0, 100, 0, 127))


def midi2percent(val):
    return round(scale(val, 0, 127, 0, 100))


def midi2note(val, with_octave=True):
    if val == '' or val < 0:
        return '-'

    note = MIDI_NOTES[val % 12]
    if not with_octave:
        return note

    octave = val // 12 - 5
    if octave == 0:
        octave = ''
    else:
        octave = '({}{}) '.format('+' if octave > 0 else '', octave)
    return '{}{:2}'.format(octave, note)


def scale(value, from_min, from_max, to_min, to_max):
    if value < from_min:
        value = from_min
    elif value > from_max:
        value = from_max
    from_span = from_max - from_min
    to_span = to_max - to_min
    scaled = float(value - from_min) / float(from_span)
    return to_min + (scaled * to_span)


def textdivide(text1, text2, width, split, ellipsis='', divider='/'):
    if split > width:
        split = width
    t1 = text1[:split]
    if len(ellipsis) and len(t1) != len(text1):
        t1 = t1[:-len(ellipsis)]
        if t1:
            t1 += ellipsis
    if t1:
        line = t1 + divider
    else:
        line = ''
    rest = max(0, width - len(line))
    t2 = text2[:rest]
    if len(ellipsis) and len(t2) != len(text2):
        t2 = t2[:-len(ellipsis)] + ellipsis
    line += t2
    return line


class PeriodicTimer(Thread):
    def __init__(self, period, callback, *args, **kwargs):
        Thread.__init__(self, name='mg-ptimer')
        self.daemon = True

        self.stopped = Event()
        self.period = period

        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def run(self):
        prctl.set_name(self.name)
        self.callback(*self.args, **self.kwargs)
        while not self.stopped.wait(self.period):
            self.callback(*self.args, **self.kwargs)

    def stop(self):
        self.stopped.set()


def debounce(wait, immediate=True):
    """
    Decorator that will postpone a functions execution until after wait seconds
    have elapsed since the last time it was invoked.

    By default it calls the function once and then again after wait seconds, if
    additional calls to the function were made in that period. To disable the
    leading call, set immediate to False

    Note that the function is always being called from the timer thread, so the
    decorated function needs to be thread-safe!
    """

    def decorator(fn):
        def debounced(*args, **kwargs):
            def call_it():
                if immediate:
                    debounced.time = time.time()
                fn(*args, **kwargs)

            timer = getattr(debounced, 'timer', None)
            if timer:
                timer.cancel()

            if immediate and ((time.time() - getattr(debounced, 'time', 0)) > wait):
                delay = 0
            else:
                delay = wait
            debounced.timer = Timer(delay, call_it)
            debounced.timer.start()
        return debounced
    return decorator


def background_task():
    def decorator(fn):
        def backgrounded(*args, **kwargs):
            decorator.task = Thread(target=fn, args=args, kwargs=kwargs)
            decorator.task.start()
        return backgrounded
    return decorator


class OneLineExceptionFormatter(logging.Formatter):
    def formatException(self, exc_info):
        result = super().formatException(exc_info)
        return repr(result)

    def format(self, record):
        s = super().format(record)
        if record.exc_text:
            s = s.replace('\n', ' ')
        return s
