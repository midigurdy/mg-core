from setuptools import setup, find_packages

setup(
    name="mgurdy",
    version="1.2.2",
    author="Marcus Weseloh",
    author_email="marcus@weseloh.cc",
    description="The main MidiGurdy program",
    license="GPL3",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={
        'mg.ui.display': ['fonts/*.bdf'],
        'mg': [
            'data/config/input.json',
            'data/config/midi.json'
        ],
    },
    include_package_data=True,
    scripts=[
        'bin/mgurdy.py',
        'bin/mgmessage.py',
        'bin/mgsysinfo.py',
    ],
    install_requires=[
        'marshmallow',
        'flask',
        'peewee',
        'cffi>=1.0.0',
    ],
    setup_requires=[
        "cffi>=1.0.0"
    ],
    cffi_modules=[
        "src/mg/mglib/mglib_build.py:ffibuilder",
        "src/mg/fluidsynth/fluidsynth_build.py:ffibuilder",
        "src/mg/alsa/alsa_build.py:ffibuilder",
    ],
)
