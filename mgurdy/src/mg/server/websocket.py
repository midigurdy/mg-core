import asyncio
import json
import threading
import websockets
import prctl
import time

from mg.signals import signals
from mg.version import VERSION
from mg.utils import PeriodicTimer


LOOP = asyncio.new_event_loop()

THROTTLE_DEFAULT = 0
THROTTLE_ALWAYS = 1

WS_EVENTS = {
    'active:preset:changed': THROTTLE_DEFAULT,
    'preset:added': THROTTLE_DEFAULT,
    'preset:deleted': THROTTLE_DEFAULT,
    'preset:changed': THROTTLE_DEFAULT,
    'preset:reordered': THROTTLE_DEFAULT,
    'sound:added': THROTTLE_DEFAULT,
    'sound:deleted': THROTTLE_DEFAULT,
    'sound:changed': THROTTLE_DEFAULT,
    'main_volume:changed': THROTTLE_ALWAYS,
    'reverb_volume:changed': THROTTLE_ALWAYS,
    'chien_threshold:changed': THROTTLE_ALWAYS,
    'coarse_tune:changed': THROTTLE_ALWAYS,
    'pitchbend_range:changed': THROTTLE_ALWAYS,
    'fine_tune:changed': THROTTLE_ALWAYS,
    'synth:gain:changed': THROTTLE_ALWAYS,
}


class WebSocketServer(threading.Thread):
    def __init__(self, port=9001):
        super().__init__(name='mg-ws-server')
        self.daemon = True
        self.port = port

    def run(self):
        prctl.set_name(self.name)
        asyncio.set_event_loop(LOOP)
        start_server = websockets.serve(ws_handler, '0.0.0.0', self.port)
        LOOP.run_until_complete(start_server)
        LOOP.run_forever()


class WebSocketQueue:
    def __init__(self, client_id):
        self.queue = asyncio.Queue()
        self.client_id = client_id
        self.throttle = {}
        self.pending = {}
        self.throttle_timeout = 0.5
        self.throttle_lock = threading.RLock()
        self.pending_timer = PeriodicTimer(self.throttle_timeout, self.send_pending)

    def start_pending_timer(self):
        self.pending_timer.start()

    def stop_pending_timer(self):
        self.pending_timer.stop()

    def put(self, item):
        LOOP.call_soon_threadsafe(self.queue.put_nowait, item)

    def get(self):
        return self.queue.get()

    def handle_event(self, name, data, force=False):
        if name not in WS_EVENTS:
            if name.startswith('active:preset:'):
                name = 'active:preset:changed'
                data = {'client_id': data.pop('client_id', None)}
            else:
                return
        data.pop('sender', None)  # no need to send this back to ui
        if not force and not self.throttle_event(name, data):
            return
        if data.pop('client_id', '') == self.client_id:
            return  # we don't want to send messages back to orignating client
        self.put({'name': name, 'data': data})

    def send_pending(self):
        with self.throttle_lock:
            if not self.pending:
                return
            now = time.time()
            names = list(self.pending.keys())
            for name in names:
                (ts, data) = self.pending[name]
                if now - ts > self.throttle_timeout or WS_EVENTS.get(name) == THROTTLE_ALWAYS:
                    self.handle_event(name, data, force=True)
                    del self.pending[name]

    def throttle_event(self, name, data):
        with self.throttle_lock:
            now = time.time()
            if WS_EVENTS.get(name) == THROTTLE_ALWAYS:
                self.pending[name] = (now, data)
                return
            prev = self.throttle.get(name)
            if prev is not None:
                if now - prev > self.throttle_timeout:
                    self.throttle[name] = now
                    return True
                else:
                    self.pending[name] = (now, data)
            else:
                self.throttle[name] = now
                if name in self.pending:
                    del self.pending
                return True


async def ws_handler(websocket, path):
    data = await websocket.recv()
    msg = json.loads(data)

    wsq = WebSocketQueue(client_id=msg['data']['id'])
    signals.register('__all__', wsq.handle_event)

    await websocket.send(json.dumps({
        'name': 'sysinfo',
        'data': {
            'name': 'MidiGurdy',
            'version': VERSION,
        }
    }))

    try:
        wsq.start_pending_timer()
        while True:
            entry = await wsq.get()
            await websocket.send(json.dumps(entry))
    except Exception as e:
        print('exception in ws loop', str(e))
    finally:
        wsq.stop_pending_timer()
        signals.unregister('__all__', wsq.handle_event)
