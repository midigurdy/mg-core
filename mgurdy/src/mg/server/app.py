import os

from flask import Flask, send_from_directory

# Using flask-static as dummy
app = Flask(__name__, static_url_path='/flask-static')

from mg.server.views import api  # noqa
from mg.conf import settings  # noqa

app.register_blueprint(api.views, url_prefix='/api')


@app.route('/download/sounds/<filename>')
def download_sound(filename):
    return send_from_directory(settings.sound_dir, filename)


@app.after_request
def send_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,mg-client-id')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory(settings.webroot_dir, os.path.join('static', path))


@app.route('/favicon.ico')
def send_favicon():
    return send_static('favicon.ico')


# All other URLs should return the index page
@app.route('/', defaults={'dummy': ''})
@app.route('/<path:dummy>')
def catch_all(dummy):
    return send_from_directory(settings.webroot_dir, 'index.html')
