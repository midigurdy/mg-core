import json
import logging
import subprocess
import threading
import time

from mg.conf import find_config_file
from mg.db import Preset
from mg.input import Action, Key
from mg.input.midi import MidiInput


log = logging.getLogger('eventhandler')


class EventHandler:
    """
    Main loop and system-wide handler for all events.

    It dispatches events to the relevant subsystems based on the event type.
    """
    def __init__(self, queue, state, menu, input_manager):
        self.state = state
        self.queue = queue
        self.menu = menu
        self.input_manager = input_manager
        self.mod_keys = 0
        self.poweroff_timer = None
        self.state_action_handler = StateActionHandler(self.state, self.menu)

    def mainloop(self):
        while True:
            try:
                evt = self.queue.get()
                if evt.type == 'input':
                    self.handle_input_event(evt)
                elif evt.type == 'state':
                    self.menu.handle_state_event(evt)
                elif evt.type == 'state_change':
                    self.handle_state_change_event(evt)
                elif evt.type == 'state_action':
                    self.handle_state_action_event(evt)
                elif evt.type == 'mdev':
                    self.handle_mdev_event(evt)
                else:
                    raise RuntimeError('Invalid event type %s' % evt.type)
            except KeyboardInterrupt:
                return
            except:
                log.exception('Error in event handler')

    def handle_state_change_event(self, evt):
        entry = self.state.attr_by_path(evt.name)
        if entry:
            with self.state.lock():
                setattr(entry['obj'], entry['attr'], evt.value)

    def handle_state_action_event(self, evt):
        method = getattr(self.state_action_handler, evt.name, None)
        if not method:
            log.error('Invalid state_action "{}"'.format(evt.name))
        else:
            method(evt.value)

    def handle_mdev_event(self, evt):
        if evt.subsystem != 'midi':
            return
        if evt.action == 'add' and evt.source == 'external':
            filename = find_config_file('midi.json')
            try:
                with open(filename, 'rb') as f:
                    config = json.load(f)
            except:
                log.exception('Unable to open midi device config')
                return
            config['device'] = evt.device
            inp = MidiInput.from_config(config)
            self.input_manager.register(inp)
        elif evt.action == 'remove' and evt.source == 'external':
            self.input_manager.unregister(evt.device)

    def poweroff_prompt(self):
        from mg.ui.pages.main import PoweroffPage
        self.menu.push(PoweroffPage())
        self.poweroff_timer = threading.Timer(2, self.poweroff)
        self.poweroff_timer.start()

    def poweroff(self):
        self.poweroff_timer = None
        self.menu.message('Powering off...', modal=True)
        subprocess.call(['/sbin/poweroff'])

    def handle_input_event(self, evt):
        if evt.name == Key.fn4:
            if evt.action == Action.down:
                if not self.poweroff_timer:
                    self.poweroff_timer = threading.Timer(1, self.poweroff_prompt)
                    self.poweroff_timer.start()
            elif evt.action == Action.up:
                if self.poweroff_timer:
                    self.poweroff_timer.cancel()
                    self.poweroff_timer = None

        # give the current menu page a chance to react to the event
        if self.menu.handle_event(evt):
            self.menu.last_input_time = time.time()
            return

        # lid buttons toggle string state
        if evt.short_pressed(Key.top1):
            self.state.toggle_voice_mute('trompette')
            return
        if evt.long_pressed(Key.top1):
            self.state.toggle_voice_mute('trompette', whole_group=True)
            return
        if evt.short_pressed(Key.top2):
            self.state.toggle_voice_mute('melody')
            return
        if evt.long_pressed(Key.top2):
            self.state.toggle_voice_mute('melody', whole_group=True)
            return
        if evt.short_pressed(Key.top3):
            self.state.toggle_voice_mute('drone')
            return
        if evt.long_pressed(Key.top3):
            self.state.toggle_voice_mute('drone', whole_group=True)
            return

        # lid modifier buttons toggle active string group
        if evt.name in (Key.mod1, Key.mod2):
            if evt.action == Action.down:
                self.mod_keys |= 1 if evt.name == Key.mod1 else 2
            elif evt.action == Action.up:
                self.mod_keys &= 2 if evt.name == Key.mod1 else 1
            group = min([self.mod_keys, 2])
            self.state.ui.string_group = group
            return


class StateActionHandler:
    """
    Provides actions that affect the state of the instrument. Mainly used
    for triggering actions from an external MIDI device
    """
    def __init__(self, state, menu):
        self.state = state
        self.menu = menu

    def load_preset(self, preset_number):
        preset = Preset.get(Preset.number == int(preset_number))
        with self.menu.lock_state('Loading preset...'):
            self.state.load_preset(preset.id)

    def toggle_string_mute(self, string_number):
        """
        Toggle the string muted state, strings identified by string number:
            1-3: melody, 4-6: drone, 7-9: trompette, 10: keynoise
        """
        voice = self.state.preset.voice_by_number(string_number)
        if voice:
            voice.muted = not voice.muted
