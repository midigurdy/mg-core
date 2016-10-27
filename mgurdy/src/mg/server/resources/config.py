from flask import request, Response
from flask_restful import abort

from mg import db
from mg import schema
from mg.input import calibration
from mg.mglib import mgcore
from mg.signals import signals

from .base import StateResource


class ImportExportView(StateResource):
    """
    Used to export or import the current setup as json, including
    all presets, all current mappings, key calibration
    """
    def get(self):
        export = {}

        if opt_switch('presets'):
            data = []
            for preset in db.Preset.select():
                entry = preset.get_data()
                entry['name'] = preset.name
                data.append(entry)
            if data:
                export['presets'] = data

        if opt_switch('mappings'):
            data = []
            for name in mgcore.get_mapping_configs().keys():
                ranges = db.load_mapping_ranges(name)
                if ranges:
                    data.append({
                        'name': name,
                        'ranges': ranges,
                    })
            if data:
                export['mappings'] = data

        if opt_switch('calibration'):
            data = db.load_key_calibration()
            if data:
                export['calibration'] = data

        if opt_switch('settings'):
            data = db.load_misc_config()
            if data:
                export['settings'] = data

        export = schema.ExportSchema().dumps(export).data

        return Response(export, mimetype='application/json', headers={
                'Content-Disposition': 'attachment;filename=midigurdy-config.json'
        })

    @db.DB.atomic()
    def post(self):
        raw_data = request.get_json()
        if not raw_data:
            abort(400, message='Please supply a preset!')
        data, errors = schema.ExportSchema().load(raw_data)
        if errors:
            abort(400, errors=errors)

        if opt_switch('presets'):
            for preset in db.Preset.select():
                preset.delete_instance()
                signals.emit('preset:deleted', {'id': preset.id})

            for preset_data in data.get('presets', []):
                name = preset_data.pop('name', '')
                preset = db.Preset(name=name)
                preset.set_data(preset_data)
                preset.save(force_insert=True)
                signals.emit('preset:added', {'id': preset.id})

        if opt_switch('mappings'):
            mapping_configs = mgcore.get_mapping_configs()
            for name in mapping_configs.keys():
                db.delete_mapping_ranges(name)
                mgcore.reset_mapping_ranges(name)
            for mapping in data.get('mappings', []):
                name = mapping['name']
                if name in mapping_configs:
                    db.save_mapping_ranges(name, mapping['ranges'])
                    mgcore.set_mapping_ranges(name, mapping['ranges'])

        if opt_switch('calibration'):
            db.delete_key_calibration()
            calib = data.get('calibration', [])
            if calib:
                db.save_key_calibration(calib)
            else:
                calib = calibration.default_keys()
            calibration.commit_keys(calib)

        if opt_switch('settings'):
            misc = data.get('settings', [])
            if misc:
                self.state.from_misc_dict(misc)
                db.save_misc_config(misc)

        return {'message': 'success'}


def opt_switch(name):
    return request.args.get(name, '') in ('true', 1, '1')
