from flask_restful import Resource


from mg.version import VERSION


class SystemInfo(Resource):
    def get(self):
        return {
            'version': VERSION,
            'name': 'MidiGurdy',
        }
