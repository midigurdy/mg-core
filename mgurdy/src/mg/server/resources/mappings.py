import logging

from flask import request
from flask_restful import Resource, abort

from mg.mglib import mgcore
from mg.mglib.api import MAPPINGS
from mg import db
from mg import schema

log = logging.getLogger('api')


class MappingList(Resource):
    def get(self):
        result = []
        for name in sorted(MAPPINGS.keys()):
            result.append(get_mapping_as_json(name))
        return result


class Mapping(Resource):
    def get(self, name):
        if name not in MAPPINGS:
            abort(404, message='Invalid mapping name')
        return get_mapping_as_json(name)

    def put(self, name):
        if name not in MAPPINGS:
            abort(404, message='Invalid mapping name')
        data = request.get_json()
        errors = schema.MappingSchema().validate(data)
        if errors:
            abort(400, errors=errors)
        ranges = data['ranges']
        try:
            mgcore.set_mapping_ranges(name, ranges)
        except:
            abort(400, message='Unable to apply mapping values')
        try:
            db.save_mapping_ranges(name, ranges)
        except:
            abort(400, message='Unable to save mapping values')
        return self.get(name)

    def delete(self, name):
        if name not in MAPPINGS:
            abort(404, message='Invalid mapping name')
        db.delete_mapping_ranges(name)
        try:
            mgcore.reset_mapping_ranges(name)
        except:
            abort(400, message='Unable to reset mapping')
        return self.get(name)


def get_mapping_as_json(name):
    result = dict(MAPPINGS[name])
    result['id'] = name
    result['ranges'] = db.load_mapping_ranges(name)

    # fallback to default ranges from mgcore if not found
    if not result['ranges']:
        result['ranges'] = mgcore.get_mapping_ranges(name)

    return result
