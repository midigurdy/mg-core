#ifndef _MG_MODEL_MIDI_H_
#define _MG_MODEL_MIDI_H_

#include "mg.h"

void model_midi_update_melody_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel, const struct mg_keyboard *kb);

void model_midi_update_trompette_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel);

void model_midi_update_drone_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel);

#endif


