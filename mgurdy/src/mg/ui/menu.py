import time
import threading
from contextlib import contextmanager

from mg.input import Action, Key
from mg.input.events import StateEvent
from mg.signals import signals
from mg.ui.pages.main import MessagePage
from mg.utils import PeriodicTimer


class Menu:
    def __init__(self, event_queue, state, display=None):
        self.event_queue = event_queue
        self.state = state
        self.named_pages = {}
        self.page_stack = []
        self.display = display
        self.page_lock = threading.RLock()
        self.last_input_time = 0
        self.idle_timer = PeriodicTimer(1, self.check_idle)
        self.idle_timer.start()

        signals.register('state:locked', self.enqueue_state_event)
        signals.register('state:unlocked', self.enqueue_state_event)

    def check_idle(self):
        with self.page_lock:
            page = self.current_page()
            if not page or not page.idle_timeout:
                return

            if time.time() - self.last_input_time > page.idle_timeout:
                page.timeout()

    def register_page(self, name, page_class):
        self.named_pages[name] = page_class

    def handle_event(self, evt):
        handled = False
        with self.page_lock:
            for page in reversed(self.page_stack):
                if page.handle(evt):
                    handled = True
                    break
        if handled:
            return True

        # global menu pages
        if evt.short_pressed(Key.back):
            self.pop()
            return True
        if evt.long_pressed(Key.back):
            self.goto('home')
            return True
        if evt.pressed(Key.fn1):
            self.goto('drone')
            return True
        if evt.pressed(Key.fn2):
            self.goto('melody')
            return True
        if evt.pressed(Key.fn3):
            self.goto('trompette')
            return True
        if evt.name == Key.fn4 and evt.action == Action.down:
            self.goto('config')
            return True
        if evt.pressed(Key.select):
            self.goto('volume')
            return True

        # turning the encoder automatically switches to chien sensitivity page
        if evt.name == Key.encoder:
            self.push('chien_threshold')
            return True

    def handle_state_event(self, evt):
        if evt.name == 'state:locked':
            self.push(MessagePage(evt.data['message'], modal=True))
        elif evt.name == 'state:unlocked':
            self.pop()
        page = self.current_page()
        page.handle_state_event(evt.name, evt.data)

    def current_page(self):
        with self.page_lock:
            if self.page_stack:
                return self.page_stack[-1]

    def push(self, page):
        with self.page_lock:
            if isinstance(page, str):
                page = self.page_by_name(page)
            parent = self.current_page()
            if parent:
                self.hide_page(parent)
            self.page_stack.append(page)
            page.init(self, self.state)
            self.show_page(page)

    def pop(self, render=True, upto=None):
        with self.page_lock:
            if self.page_stack:
                if upto:
                    self._clear_page_stack(upto=upto)
                    child = upto
                else:
                    child = self.page_stack.pop()
                    self.hide_page(child)
                current = self.current_page()
                if current:
                    self.show_page(current, render=render, from_child=child)
                    return

            self.goto('home')

    def goto(self, page):
        with self.page_lock:
            if isinstance(page, str):
                page = self.page_by_name(page)
            self._clear_page_stack()
            self.push(page)

    def page_by_name(self, name):
        page_class = self.named_pages[name]
        return page_class()

    def show_page(self, page, *args, **kwargs):
        page.show(*args, **kwargs)

    def hide_page(self, page):
        page.hide()

    def enqueue_state_event(self, name, data):
        event = StateEvent(name, data)
        self.event_queue.put(event)

    def _clear_page_stack(self, upto=None):
        first = True
        while self.page_stack:
            page = self.page_stack.pop()
            if first:
                self.hide_page(page)
                first = False
            if upto and upto == page:
                return

    def message(self, message, timeout=0, popup=False, modal=False, font_size=3):
        page = MessagePage(message, modal, font_size)
        if timeout:
            self.last_input_time = time.time()
            page.idle_timeout = timeout
        if popup:
            self.push(page)
        else:
            self.goto(page)

    @contextmanager
    def lock_state(self, message):
        with self.state.lock():
            page = MessagePage(message)
            self.push(page)
            try:
                yield
            finally:
                self.pop()

    def cleanup(self):
        signals.unregister('state:locked', self.enqueue_state_event)
        signals.unregister('state:unlocked', self.enqueue_state_event)
        page = self.current_page()
        if page:
            page.hide()
