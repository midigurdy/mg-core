import os


class Settings:
    def __init__(self):
        self.set_defaults()

    def set_defaults(self):
        self.set_data_dir('/data')
        self.http_port = 80
        self.webroot_dir = '/srv/www'
        self.input_config = 'input.json'
        self.debug = False

    def set_data_dir(self, data_dir):
        self.data_dir = data_dir
        self.sound_dir = os.path.join(data_dir, 'sounds')
        self.config_dir = os.path.join(data_dir, 'config')
        self.upload_dir = os.path.join(data_dir, 'uploads')

    def create_dirs(self):
        for path in (self.sound_dir, self.config_dir, self.upload_dir):
            if not os.path.exists(path):
                os.makedirs(path)

    @property
    def dist_data_dir(self):
        return os.path.join(os.path.dirname(__file__), 'data')

    @property
    def dist_config_dir(self):
        return os.path.join(self.dist_data_dir, 'config')


settings = Settings()


def find_config_file(name):
    path = os.path.join(settings.config_dir, name)
    if os.path.isfile(path):
        return path

    path = os.path.join(settings.dist_config_dir, name)
    if os.path.isfile(path):
        return path
