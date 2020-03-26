import os
import configparser

SETTINGS = (
    # section, key, type, default
    ('core', 'data_dir', 'str', '/data'),
    ('core', 'sound_dir', 'str', '/data/sounds'),
    ('core', 'config_dir', 'str', '/data/config'),
    ('core', 'upload_dir', 'str', '/data/uploads'),
    ('core', 'input_config', 'str', 'input.json'),

    ('server', 'http_port', 'int', 80),
    ('server', 'webroot_dir', 'str', '/srv/www'),

    ('system', 'power_state_ac', 'str', '/sys/class/power_supply/axp20x-ac/online'),
    ('system', 'power_state_usb', 'str', '/sys/class/power_supply/axp20x-usb/online'),
    ('system', 'battery_voltage', 'str',  '/sys/class/hwmon/hwmon0/in1_input'),
    ('system', 'backlight_control', 'str', '/sys/class/backlight/ssd1307fb0/brightness'),
    ('system', 'led_brightness_1', 'str', '/sys/class/leds/string1/brightness'),
    ('system', 'led_brightness_2', 'str', '/sys/class/leds/string2/brightness'),
    ('system', 'led_brightness_3', 'str', '/sys/class/leds/string3/brightness'),
    ('system', 'alsa_mixer', 'str', 'Power Amplifier'),
    ('system', 'udc_config', 'str', '/sys/devices/platform/soc@01c00000/1c13000.usb/musb-hdrc.1.auto/gadget/configuration'),
    ('system', 'display_device', 'str', '/dev/fb0'),
    ('system', 'display_mmap', 'boolean', True),

    ('logging', 'log_method', 'str', 'syslog'),
    ('logging', 'log_level', 'str', 'WARNING'),
    ('logging', 'log_file', 'str', '/dev/log'),
    ('logging', 'log_oneline', 'boolean', True),
    ('logging', 'log_levels', 'str', ''),
)


class Settings:
    def __init__(self):
        self.set_defaults()

    def set_defaults(self):
        self.debug = False

        for _, key, _, default in SETTINGS:
            setattr(self, key, default)

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

    def load(self, filename):
        config = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
        if not config.read(filename):
            raise FileNotFoundError(filename)

        for section, key, keytype, default in SETTINGS:
            if keytype == 'str':
                keytype = ''
            if config.has_option(section, key):
                try:
                    getter = getattr(config, f'get{keytype}')
                    setattr(self, key, getter(section, key))
                except Exception as e:
                    raise Exception(f'Error parsing config {section}:{key}') from e


settings = Settings()


def find_config_file(name):
    path = os.path.join(settings.config_dir, name)
    if os.path.isfile(path):
        return path

    path = os.path.join(settings.dist_config_dir, name)
    if os.path.isfile(path):
        return path
