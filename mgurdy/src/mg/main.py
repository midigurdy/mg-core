import logging.config
import os
import argparse
import prctl

from mg.utils import background_task
from mg.conf import settings, find_config_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--uitest', action='store_true')
    parser.add_argument('--noui', action='store_true')
    parser.add_argument('--input-config', default='input.json')
    parser.add_argument('--dump-midi', action='store_true')
    parser.add_argument('--debug-fs', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--data-dir', default='/data')
    parser.add_argument('--webroot-dir', default='/srv/www')
    parser.add_argument('--http-port', default=80)
    parser.add_argument('--traceback', action='store_true')
    args = parser.parse_args()

    try:
        start(args)
    except Exception as e:
        if args.traceback:
            raise
        else:
            import sys
            sys.stderr.write('{}'.format(e))
            sys.exit(2)


def start(args):
    prctl.set_proctitle('mg-main')
    prctl.set_name('mg-main')

    configure_logging(debug=args.debug)

    for key in ('webroot_dir', 'http_port', 'input_config'):
        setattr(settings, key, getattr(args, key))
    settings.set_data_dir(args.data_dir)
    settings.create_dirs()

    from mg.fluidsynth.api import FluidSynth
    from mg.state import State
    from mg.controller import SynthController, SystemController, MIDIController

    state = State()

    menu, input_manager, event_handler = start_ui(
        state=state,
        ui_test=args.uitest,
        no_ui=args.noui)

    fluid = FluidSynth()

    synth_ctrl = SynthController(fluid, state)
    synth_ctrl.start_listening()

    system_ctrl = SystemController(state)
    system_ctrl.start_listening()
    system_ctrl.set_string_led(1, 0)
    system_ctrl.set_string_led(2, 0)
    system_ctrl.set_string_led(3, 0)
    system_ctrl.update_udc_configuration()

    midi_ctrl = MIDIController(input_manager)
    midi_ctrl.start_listening()

    menu.message('Starting synthesizer')
    start_fluidsynth(
        fluid,
        dump_midi=args.dump_midi,
        debug=args.debug_fs)

    menu.message('Starting core')
    from mg.mglib import mgcore
    mgcore.start(fluid)

    menu.message('Opening database')
    from mg import db
    import logging
    log = logging.getLogger()
    db_path = os.path.join(settings.data_dir, 'mg.db')
    try:
        db.initialize(db_path)
    except:
        log.exception('Unable to initialize database!')
    db.migrate(db_path)

    # restore key calibration
    from mg.input import calibration
    key_calib = calibration.load_keys()
    calibration.commit_keys(key_calib)

    # restore mapping ranges
    for name in mgcore.get_mapping_configs().keys():
        ranges = db.load_mapping_ranges(name)
        if ranges:
            mgcore.set_mapping_ranges(name, ranges)

    menu.message('Loading preset')

    # set default global settings
    state.main_volume = 120
    state.reverb_volume = 25
    state.preset.keynoise[0].volume = 25
    state.coarse_tune = 0
    state.fine_tune = 0
    state.ui.brightness = 80
    state.synth.gain = 50
    state.pitchbend_range = 100

    # restore misc config
    misc = db.load_misc_config()
    if misc:
        state.from_misc_dict(misc)

    try:
        preset = db.Preset.get()  # noqa
        with state.lock():
            state.load_preset(preset.id)
    except db.Preset.DoesNotExist:
        pass

    menu.message('Starting server')
    start_server(state, menu)

    menu.goto('home')
    input_manager.start()

    event_handler.mainloop()


@background_task()
def start_server(state, menu):
    from mg.server.web import WebServer
    from mg.server.websocket import WebSocketServer

    web = WebServer(state=state, menu=menu, port=settings.http_port)
    web.start()
    ws = WebSocketServer()
    ws.start()


def start_fluidsynth(synth, dump_midi, debug=False):
    if debug:
        synth.set_logger()
    synth.configure({
        "audio.driver": "alsa",
        "audio.periods": 2,
        "audio.period-size": 64,
        "audio.realtime-prio": 51,
        "synth.reverb.active": 0,
        "synth.chorus.active": 0,
        "synth.ladspa.active": 1,
        "synth.overflow.important": 50000,
        "synth.overflow.important-channels": '4,5,6,7,8,9',
        "synth.min-note-length": 0,
        "synth.verbose": 1 if dump_midi else 0,
        "synth.polyphony": 64,
        "synth.dynamic-sample-loading": 1,
    })
    synth.start()

    # FIXME: make the effects configurable via web
    synth.ladspa.add_effect('e1', '/usr/lib/ladspa/filter.so', 'hpf')
    synth.ladspa.link_effect('e1', 'Input', 'Reverb:Send')
    synth.ladspa.link_effect('e1', 'Output', 'Reverb:Send')
    synth.ladspa.set_control('e1', 'Cutoff', 220)

    synth.ladspa.add_effect('sympa', '/usr/lib/ladspa/sympathetic.so', mix=True)
    synth.ladspa.link_effect('sympa', 'Input', 'Reverb:Send')
    synth.ladspa.link_effect('sympa', 'Output Left', 'Main:L')
    synth.ladspa.link_effect('sympa', 'Output Right', 'Main:R')
    synth.ladspa.set_control('sympa', 'Damping', 0.06)

    synth.ladspa.activate()


def start_ui(state, ui_test, no_ui):
    from queue import Queue

    from mg.input.manager import InputManager
    from mg.input.mdev import MdevInput
    from mg.ui.display import Display

    from mg.handler import EventHandler
    from mg.ui.menu import Menu
    from mg.ui.pages.main import Home, VolumeDeck, ChienThresholdPage, MultiChienThresholdPage
    from mg.ui.pages.config import PresetConfigDeck
    from mg.ui.pages.strings import MelodyDeck, DroneDeck, TrompetteDeck

    if no_ui:
        from mg.ui.display.base import BaseDisplay
        display = BaseDisplay(128, 32)
    elif ui_test:
        display = Display(128, 32, '/tmp/mgimage', mmap=False)
    else:
        display = Display(128, 32, '/dev/fb0', mmap=True)

    event_queue = Queue()

    menu = Menu(event_queue, state, display)
    menu.debug = ui_test
    menu.register_page('home', Home)
    menu.register_page('melody', MelodyDeck)
    menu.register_page('drone', DroneDeck)
    menu.register_page('trompette', TrompetteDeck)
    menu.register_page('config', PresetConfigDeck)
    menu.register_page('volume', VolumeDeck)
    menu.register_page('chien_threshold', ChienThresholdPage)
    menu.register_page('multi_chien_threshold', MultiChienThresholdPage)
    menu.goto('home')

    input_manager = InputManager(event_queue)
    config_filename = find_config_file(settings.input_config)
    input_manager.load_config(config_filename)
    input_manager.register(MdevInput('/tmp/mgurdy', 'mdev Input Handler'))

    event_handler = EventHandler(event_queue, state, menu)

    return menu, input_manager, event_handler


def configure_logging(debug=False):
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'class': 'mg.utils.OneLineExceptionFormatter',
                'format': '{asctime} {levelname} - {name} - {processName} - {message}',
                'style': '{',
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'default',
            },
        },
        'loggers': {
            'system': {
                'level': 'CRITICAL' if debug else 'WARNING',
                'formatter': 'default',
            },
            'signals': {
                'level': 'DEBUG' if debug else 'WARNING',
                'formatter': 'default',
            },
            'fluidsynth': {
                'level': 'DEBUG' if debug else 'WARNING',
                'formatter': 'default',
            },
        },
        'root': {
            'level': 'WARNING',
            'handlers': ['console'],
        },
    })
