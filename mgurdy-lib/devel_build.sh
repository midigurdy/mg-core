#!/bin/bash

export LIBRARY_PATH=../../fluidsynth/build/src
export C_INCLUDE_PATH=../../fluidsynth/include:../../fluidsynth/build/include

make $*
