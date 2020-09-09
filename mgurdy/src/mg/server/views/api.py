from flask import Blueprint
from flask_restful import Api

from mg.server.resources.mappings import Mapping, MappingList
from mg.server.resources import presets
from mg.server.resources import sounds
from mg.server.resources import instrument
from mg.server.resources.info import SystemInfo
from mg.server.resources import calibration
from mg.server.resources import config
from mg.server.resources import misc
from mg.server.resources.display import DisplayView

views = Blueprint('api', __name__)
api = Api(views)

api.add_resource(MappingList, '/mappings')
api.add_resource(Mapping, '/mappings/<string:name>')

api.add_resource(presets.PresetListView, '/presets')
api.add_resource(presets.PresetView, '/presets/<int:id>')
api.add_resource(presets.LoadPresetView, '/presets/<int:id>/load')
api.add_resource(presets.OrderPresetsView, '/presets/order')

api.add_resource(sounds.SoundFontListView, '/sounds')
api.add_resource(sounds.SoundFontView, '/sounds/<string:id>')
api.add_resource(sounds.SoundFontUploadView,
                 '/upload/sound/<string:filename>')

api.add_resource(instrument.InstrumentView, '/instrument')

api.add_resource(config.ImportExportView, '/config')

api.add_resource(misc.MiscView, '/misc')

api.add_resource(calibration.Keyboard, '/calibrate/keyboard')
api.add_resource(calibration.Wheel, '/calibrate/wheel')

api.add_resource(SystemInfo, '/info')

api.add_resource(DisplayView, '/screenshot')
