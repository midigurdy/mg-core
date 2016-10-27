import os


class Settings:
    def __init__(self):
        self.set_defaults()

    def set_defaults(self):
        self.set_data_dir('/data')
        self.http_port = 80
        self.webroot_dir = '/srv/www'
        self.input_config = 'input'
        self.debug = False

    def set_data_dir(self, data_dir):
        self.data_dir = data_dir
        self.sound_dir = os.path.join(data_dir, 'sounds')
        self.config_dir = os.path.join(data_dir, 'config')
        self.upload_dir = os.path.join(data_dir, 'uploads')

    @property
    def input_config_file(self):
        return os.path.join(self.config_dir, '{}.json'.format(
            self.input_config))

    @property
    def dist_data_dir(self):
        return os.path.join(os.path.dirname(__file__), 'data')

    @property
    def dist_config_dir(self):
        return os.path.join(self.dist_data_dir, 'config')


settings = Settings()
