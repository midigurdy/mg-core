#!/bin/bash

export LIBRARY_PATH=~../../fluidsynth/build/src:~/../mgurdy-lib/build
export C_INCLUDE_PATH=~../../fluidsynth/build/include:../../fluidsynth/include:~../mgurdy-lib/src:/usr/include/freetype2

python setup.py develop
