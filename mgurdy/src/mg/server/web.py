import logging
import threading
from flask import request
import prctl

from mg.db import DB
from mg.signals import signals

from .app import app


log = logging.getLogger('web')


class WebServer(threading.Thread):
    def __init__(self, state, menu, port=80, debug=None):
        super().__init__(name='mg-web-server')
        self.state = state
        self.menu = menu
        self.daemon = True
        self.port = port
        self.debug = debug

    def run(self):
        prctl.set_name(self.name)
        try:
            app.config['state'] = self.state
            app.config['menu'] = self.menu
            app.run(port=self.port, host='0.0.0.0', debug=self.debug, threaded=True)
        except:
            log.exception('Unable to start webserver on port {}'.format(self.port))


@app.before_request
def open_db_connection():
    client_id = request.headers.get('mg-client-id', None)
    signals.set_client_id(client_id)
    DB.connect()


@app.teardown_request
def close_db_connection(exc):
    if not DB.is_closed():
        DB.close()
