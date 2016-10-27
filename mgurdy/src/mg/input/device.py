import fcntl
import os


class InputDevice:
    def __init__(self, filename, name='Input Device', debug=False):
        self.name = name
        self.debug = debug
        self.filename = filename

    @classmethod
    def from_config(cls, config):
        inp = cls(name=config['device'],
                  filename=config['device'],
                  debug=bool(config.get('debug')))
        inp.set_mappings(config['mappings'])
        return inp

    def open(self):
        self.fd = open(self.filename, 'rb', 0)
        fileno = self.fd.fileno()
        flag = fcntl.fcntl(fileno, fcntl.F_GETFL)
        fcntl.fcntl(fileno, fcntl.F_SETFL, flag | os.O_NONBLOCK)
        return self.fd

    def close(self):
        self.fd.close()

    def get_initial_events(self):
        pass
