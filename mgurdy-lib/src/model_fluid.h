#ifndef _MG_MODEL_FLUID_H_
#define _MG_MODEL_FLUID_H_

#include "mg.h"

void model_fluid_update_melody_streams(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel, const struct mg_keyboard *kb);

void model_fluid_update_trompette_streams(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel);

void model_fluid_update_drone_streams(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel);

void model_fluid_update_keynoise_stream(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel, const struct mg_keyboard *kb);

#endif

