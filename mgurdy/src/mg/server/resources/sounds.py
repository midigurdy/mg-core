import re
import os
import shutil
import tempfile

from flask import request
from flask_restful import Resource, abort

from werkzeug.utils import secure_filename

from mg.sf2 import SoundFont
from mg.signals import signals
from mg.conf import settings

from .base import StateResource


class UploadError(Exception):
    pass


class SoundFontUploadView(StateResource):
    def post(self, filename=None, overwrite=None):
        filename = secure_filename(filename)

        if not re.search(r'\.sf[23]$', filename, re.I):
            abort(400, message='Invalid file extension, please use .sf2 or .sf3 files')

        filepath = os.path.join(settings.sound_dir, filename)
        overwrite = os.path.isfile(filepath)

        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            dir=settings.upload_dir)
        try:
            while True:
                chunk = request.stream.read(16 * 1024 * 1024)
                if len(chunk) == 0:
                    break
                tmp.write(chunk)
            tmp.seek(0)

            try:
                SoundFont().parse_file(tmp)
            except Exception as e:
                raise UploadError('Invalid file format, is this really a SoundFont?')

            tmp.close()

            if os.path.isfile(filepath):
                os.unlink(filepath)
            shutil.move(tmp.name, filepath)

        except UploadError as e:
            try:
                os.unlink(tmp.name)
            except:
                pass
            abort(400, message=str(e))

        if overwrite:
            with self.state.lock('Loading...'):
                signals.emit('sound:changed', {'id': filename})
        else:
            signals.emit('sound:added', {'id': filename})

        return SoundFont(filepath).as_dict()


class SoundFontListView(Resource):
    def get(self):
        return [sf2.as_dict() for sf2 in SoundFont.load_all()]


class SoundFontView(StateResource):
    def get(self, id):
        filepath = self.id_to_filepath(id)
        if not os.path.isfile(filepath):
            return abort(404)
        try:
            return SoundFont(filepath).as_dict()
        except:
            abort(500, message='Unable to load sound')

    def delete(self, id):
        filepath = self.id_to_filepath(id)
        if not os.path.isfile(filepath):
            return abort(404)
        try:
            os.remove(filepath)
        except Exception as e:
            return abort(500, message=str(e))
        with self.state.lock('Loading...'):
            signals.emit('sound:deleted', {'id': id})
        return None, 204

    def id_to_filepath(self, id):
        filename = secure_filename(id)
        return os.path.join(settings.sound_dir, filename)
