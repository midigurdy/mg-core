from flask import current_app
from flask_restful import Resource


class StateResource(Resource):
    @property
    def state(self):
        return current_app.config['state']
