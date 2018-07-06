from flask import request
from flask_restful import Resource, abort

from playhouse.flask_utils import get_object_or_404

from mg.db import Preset
from mg.signals import signals

from .base import StateResource


class PresetListView(Resource):
    def get(self):
        return [preset.to_dict() for preset in Preset.select()]

    def post(self):
        data = request.get_json()
        if not data:
            abort(400, message='Please supply a preset!')
        errors = Preset.data_schema.validate(data)
        if errors:
            abort(400, errors=errors)
        preset = Preset(name=data.get('name'))
        preset.set_data(data)
        preset.save(force_insert=True)
        signals.emit('preset:added', {'id': preset.id})
        return preset.to_dict(), 201


class PresetView(Resource):
    def get(self, id):
        preset = get_object_or_404(Preset, Preset.id == id)
        return preset.to_dict()

    def put(self, id):
        preset = get_object_or_404(Preset, Preset.id == id)
        data = request.get_json()
        errors = Preset.data_schema.validate(data)
        if errors:
            abort(400, errors=errors)
        preset.name = data.get('name')
        preset.set_data(data)
        preset.save()
        signals.emit('preset:changed', {'id': preset.id})
        return self.get(id)

    def delete(self, id):
        preset = get_object_or_404(Preset, Preset.id == id)
        preset.delete_instance()
        signals.emit('preset:deleted', {'id': preset.id})
        return None, 204


class LoadPresetView(StateResource):
    def post(self, id):
        preset = get_object_or_404(Preset, Preset.id == id)
        with self.state.lock('Loading preset...', goto_home=True):
            self.state.load_preset(preset.id)
            signals.emit('active:preset:changed')
        return None, 204


class OrderPresetsView(Resource):
    def post(self):
        order = request.get_json()['order']
        Preset.reorder(order)
        signals.emit('preset:reordered', {'order': order})
        return {
            'order': [p.id for p in Preset.select(Preset.id)]
        }
