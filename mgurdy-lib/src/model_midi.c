#include "model_midi.h"

void model_midi_update_melody_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel,
        const struct mg_keyboard *keyboard)
{
    printf("midi melody %p - state: %p, wheel: %p, kb: %p\n", stream, state, wheel, keyboard);
}

void model_midi_update_trompette_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel)
{
    printf("midi trompette %p - state: %p, wheel: %p\n", stream, state, wheel);
}

void model_midi_update_drone_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel)
{
    printf("midi drone %p - state: %p, wheel: %p\n", stream, state, wheel);
}
