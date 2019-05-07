from io import BytesIO

from flask import request, current_app, send_file
from flask_restful import Resource

from PIL import Image


class DisplayView(Resource):
    """
    Returns a screenshot of the display on the instrument
    """
    def get(self):
        display = current_app.config['menu'].display

        width = display.width
        height = display.height
        data = display.get_image_data()
        image = Image.frombytes('1', (width, height), data, 'raw', '1;R')

        try:
            scale = int(request.args.get('scale', 1))
        except (ValueError, TypeError):
            scale = 1

        if scale != 1:
            image = image.resize((width * scale, height * scale))

        ext = request.args.get('format')
        image_format, mime_type = {
            'gif': ('GIF', 'image/gif'),
            'jpg': ('JPEG', 'image/jpeg'),
            'png': ('PNG', 'image/png'),
        }.get(ext, ('GIF', 'image/gif'))

        image_data = BytesIO()
        image.save(image_data, image_format)
        image_data.seek(0)

        return send_file(image_data, mimetype=mime_type)
