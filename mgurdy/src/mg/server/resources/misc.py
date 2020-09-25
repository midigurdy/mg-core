from flask import request
from flask_restful import abort

from mg.schema import MiscSchema
from mg import db

from .base import StateResource


class MiscView(StateResource):
    """
    Provides read and write access to the miscellaneous settings
    """
    def get(self):
        return self.state.to_misc_dict()

    def put(self):
        """
        Does a partial update on the state, only changing things that
        are actually present in the submitted JSON data.
        Changes are not saved.
        """
        data = request.get_json()
        errors = MiscSchema().validate(data)
        if errors:
            abort(400, errors=errors)
        self.state.from_misc_dict(data, partial=True)
        return self.get()

    def post(self):
        """
        Replaces the current state with the submitted data. If values are missing
        from the submitted JSON, it's set to the default value. Changes are stored
        to the database.
        """
        data = request.get_json()
        errors = MiscSchema().validate(data)
        if errors:
            abort(400, errors=errors)
        self.state.from_misc_dict(data, partial=False)
        db.save_misc_config(self.state.to_misc_dict())
        return self.get()
