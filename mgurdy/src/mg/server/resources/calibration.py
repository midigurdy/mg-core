from flask import request
from flask_restful import abort

from mg.input import calibration
from mg import db

from .base import StateResource
from .schema import KeyCalibrationSchema


class Keyboard(StateResource):
    def get(self):
        data = calibration.load_keys()
        return KeyCalibrationSchema(many=True).dump(data).data

    def put(self):
        data, errors = KeyCalibrationSchema(many=True).load(request.get_json())
        if errors:
            abort(400, errors=errors)
        calibration.save_keys(data)
        calibration.commit_keys(data)
        return self.get()

    def delete(self):
        db.delete_key_calibration()
        calibration.commit_keys(calibration.default_keys())
        return self.get()
