#ifndef _MG_OUTPUT_FLUID_H_
#define _MG_OUTPUT_FLUID_H_

#include <fluidsynth.h>

#include "output.h"


struct mg_output *new_fluid_output(struct mg_core *mg, fluid_synth_t *fluid);

#endif
