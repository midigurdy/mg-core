from flask import request
from flask_restful import abort

from mg.schema import PresetSchema
from mg.signals import signals

from .base import StateResource


class InstrumentView(StateResource):
    """
    Provides read and write access to the current instrument state, i.e.
    everything that can be saved in a Preset
    """
    def get(self):
        return self.state.to_preset_dict()

    def put(self):
        """
        Does a partial update on the preset state, only changing things that
        are actually present in the submitted JSON data
        """
        data = request.get_json()
        errors = PresetSchema().validate(data)
        if errors:
            abort(400, errors=errors)
        self.state.from_preset_dict(data, partial=True)
        return self.get()

    def post(self):
        """
        Replaces the current state with the submitted data. If values are missing
        from the submitted JSON, it's set to the default value.
        """
        data = request.get_json()
        errors = PresetSchema().validate(data)
        if errors:
            abort(400, errors=errors)
        with signals.suppress():
            self.state.from_preset_dict(data, partial=False)
        signals.emit('active:preset:changed')
        return self.get()
