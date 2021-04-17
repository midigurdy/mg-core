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
        except Exception:
            abort(400, message='Unable to apply mapping values')
        return self.get(name)

    def post(self, name):
        if name not in MAPPINGS:
            abort(404, message='Invalid mapping name')
        data = request.get_json()
        errors = schema.MappingSchema().validate(data)
        if errors:
            abort(400, errors=errors)
        ranges = data['ranges']
        try:
            mgcore.set_mapping_ranges(name, ranges)
        except Exception:
            abort(400, message='Unable to apply mapping values')
        try:
            db.save_mapping_ranges(name, ranges)
        except Exception:
            abort(400, message='Unable to save mapping values')
        return self.get(name)

    def delete(self, name):
        factory_reset = request.args.get('factory', False)
        if name not in MAPPINGS:
            abort(404, message='Invalid mapping name')
        try:
            if factory_reset:
                db.delete_mapping_ranges(name)
                mgcore.reset_mapping_ranges(name)
            else:
                ranges = db.load_mapping_ranges(name)
                if not ranges:
                    mgcore.reset_mapping_ranges(name)
                else:
                    mgcore.set_mapping_ranges(name, ranges)
        except Exception:
            raise
            abort(400, message='Unable to reset mapping')

        return self.get(name)


def get_mapping_as_json(name):
    result = dict(MAPPINGS[name])
    result['id'] = name
    result['ranges'] = mgcore.get_mapping_ranges(name)

    try:
        db_ranges = db.load_mapping_ranges(name)
    except Exception:
        db_ranges = []

    result['temporary'] = result['ranges'] != db_ranges

    return result
