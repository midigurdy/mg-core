from mg.mglib import mgcore
from mg import db


KEY_MAX_PRESSURE = 3000.0


def default_keys():
    return [{'pressure': 2000, 'velocity': 0} for i in range(24)]


def load_keys():
    calibration = db.load_key_calibration()
    return calibration or default_keys()


def save_keys(data):
    db.save_key_calibration(data)


def commit_keys(keys):
    calibration_data = []
    for key in keys:
        calibration_data.append({
            'pressure': KEY_MAX_PRESSURE / key['pressure'],
            'velocity': (key['velocity'] + 100) / 100.0,
        })
    mgcore.set_key_calibration(calibration_data)
