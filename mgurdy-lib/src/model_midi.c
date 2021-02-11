#include "model_midi.h"

#include "utils.h"
#include "state.h"


static void melody_model_generic(struct mg_voice *model, const struct mg_string *st,
        const struct mg_state *state, const struct mg_keyboard *kb,
        int expression);

static void melody_model_keyboard(struct mg_voice *model, const struct mg_string *st,
        const struct mg_state *state, const struct mg_keyboard *kb);

static void trompette_model_percussion(struct mg_voice *model,
        const struct mg_string *st, const struct mg_state *state,
        int wheel_speed);


void model_midi_update_melody_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel,
        const struct mg_keyboard *kb)
{
    const struct mg_string *st = stream->string;
    struct mg_voice *model = &stream->model;

    int expression = map_value(wheel->speed, &state->speed_to_melody_volume);

    /* If the string is muted, then there's no need to do anything */
    if (st->muted) {
        if (model->note_count > 0) {
            mg_voice_clear_notes(model);
        }
        return;
    }

    model->volume = st->volume;
    model->panning = st->panning;
    model->bank = st->bank;
    model->program = st->program;

    if (model->mode != st->mode) {
        mg_voice_clear_notes(model);
        model->mode = st->mode;
    }

    if (st->mode == MG_MODE_KEYBOARD) {
        melody_model_keyboard(model, st, state, kb);
    }
    else {  // MG_MODE_GENERIC
        melody_model_generic(model, st, state, kb, expression);
    }
}


void model_midi_update_trompette_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel)
{
    const struct mg_string *st = stream->string;
    struct mg_voice *model = &stream->model;

    /* If the string is muted, then there's no need to do any anything */
    if (st->muted) {
        if (model->note_count > 0) {
            mg_voice_clear_notes(model);
        }
        return;
    }

    model->volume = st->volume;
    model->panning = st->panning;
    model->bank = st->bank;
    model->program = st->program;

    if (model->mode != st->mode) {
        mg_voice_clear_notes(model);
        model->mode = st->mode;
    }

    /* Percussive mode, more suitable for other sounds like drums or other percussive sounds:
     * Only when the threshold is reached does a note-on occur, the velocity of the
     * note-on is calculated from the wheel speed above the threshold */
    trompette_model_percussion(model, st, state, wheel->speed);
}


void model_midi_update_drone_stream(struct mg_stream *stream,
        const struct mg_state *state, const struct mg_wheel *wheel)
{
    const struct mg_string *st = stream->string;
    struct mg_voice *model = &stream->model;

    int expression = map_value(wheel->speed, &state->speed_to_drone_volume);

    struct mg_note *note;

    if (st->muted) {
        model->expression = 0;
    } else {
        model->expression = expression;
    }

    if (model->expression <= 0) {
        if (model->note_count > 0) {
            mg_voice_clear_notes(model);
        }
        return;
    }

    model->volume = st->volume;
    model->panning = st->panning;
    model->bank = st->bank;
    model->program = st->program;

    /* No change in base note, moving on... */
    if (model->note_count > 0 && model->active_notes[0] == st->base_note) {
        return;
    }

    mg_voice_clear_notes(model);
    note = mg_voice_enable_note(model, st->base_note);
    note->velocity = 127;
}


static void melody_model_generic(struct mg_voice *model,
        const struct mg_string *st,
        const struct mg_state *state,
        const struct mg_keyboard *kb,
        int expression)
{
    struct mg_note *note;
    const struct mg_key *key;
    int key_idx;
    int key_num;

    model->expression = expression;

    /* The wheel is not moving, so we clear all notes */
    if (expression == 0) {
        mg_voice_clear_notes(model);
        return;
    }

    /* If no key is pressed or the highest key is below the capo key,
     * output the base note or capo key note. */
    if (kb->active_key_count == 0 || (kb->active_keys[kb->active_key_count - 1] < st->empty_key)) {

        model->pitch = 0x2000; // no key pressed, no pitch bend.

        /* If a base note delay is set, wait for that number of iterations before reacting */
        if (kb->inactive_count < state->base_note_delay) {
            return;
        }

        mg_voice_clear_notes(model);

        /* No base note in polyphonic mode unless enabled */
        if (st->polyphonic && !state->poly_base_note) {
            return;
        }

        /* Determine base note MIDI number, taking capo into account */
        note = mg_voice_enable_note(model, st->base_note + st->empty_key);

        /* ...and configure note parameters */
        note->velocity = 120;

        return;
    }

    /* We have at least one pressed key and the wheel is moving. */
    mg_voice_clear_notes(model);

    /* Start processing from highest to lowest key */
    key_idx = kb->active_key_count - 1;

    /* Determine string pitch using the highest key */
    key_num = kb->active_keys[key_idx];
    key = &kb->keys[key_num];

    if (st->polyphonic && !state->poly_pitch_bend) {
        model->pitch = 0x2000;
    } else {
        model->pitch = 0x2000 + (
            state->pitchbend_factor *
            map_value(key->smoothed_pressure, &state->pressure_to_pitch)
        );
    }

    /* Now go though all pressed keys in reverse order and set up the
     * corresponding notes. In monophonic mode, we do this only once for
     * the highest key. */
    do {
        key_num = kb->active_keys[key_idx];
        key = &kb->keys[key_num];

        note = mg_voice_enable_note(model, st->base_note + key_num + 1);
        note->velocity = 120;
        key_idx--;

    } while (key_idx >= 0 && st->polyphonic);
}


static void melody_model_keyboard(struct mg_voice *model, const struct mg_string *st,
        const struct mg_state *state, const struct mg_keyboard *kb)
{
    struct mg_note *note;
    const struct mg_key *key;
    int key_idx;
    int key_num;

    /* Volume is controlled via velocity */
    model->expression = 127;

    /* If no key is pressed then the string is silent, like a piano */
    if (kb->active_key_count == 0 || (kb->active_keys[kb->active_key_count - 1] < st->empty_key)) {
        model->pitch = 0x2000; // no key pressed, no pitch bend.
        mg_voice_clear_notes(model);
        return;
    }

    mg_voice_clear_notes(model);

    /* Start processing from highest to lowest key */
    key_idx = kb->active_key_count - 1;

    /* No pitch bend in keyboard mode */
    model->pitch = 0x2000;

    /* Now go though all pressed keys in reverse order and set up the
     * corresponding notes. In monophonic mode, we do this only once for
     * the highest key. */
    do {
        key_num = kb->active_keys[key_idx];
        key = &kb->keys[key_num];

        note = mg_voice_enable_note(model, st->base_note + key_num + 1);

        /* ...and configure note parameters */
        note->velocity = map_value(key->velocity, &state->keyvel_to_notevel);

        key_idx--;

    } while (key_idx >= 0 && st->polyphonic);
}


static void trompette_model_percussion(struct mg_voice *model,
        const struct mg_string *st, const struct mg_state *state,
        int wheel_speed)
{
    int velocity;
    struct mg_note *note;

    int raw_chien_speed = wheel_speed - st->threshold;

    if (raw_chien_speed < 0) {
        raw_chien_speed = 0;
    }

    // real-time volume only controlled via note-on velocity
    model->expression = 127;

    /* As we're dealing with percussive sounds, we need to debounce the
     * on / off transitions.
     * FIXME: make the debounce times configurable via the web-interface! */
    if (raw_chien_speed > 0) {
        if (model->note_count == 0) {
            if (model->chien_debounce < model->chien_on_debounce) {
                model->chien_debounce++;
                return;
            }
        }
    }
    else {
        if (model->note_count > 0) {
            if (model->chien_debounce < model->chien_off_debounce) {
                model->chien_debounce++;
                return;
            }
        }
    }

    model->chien_debounce = 0;

    if (raw_chien_speed <= 0) {
        if (model->note_count > 0) {
            mg_voice_clear_notes(model);
        }
        return;
    }

    if (model->note_count > 0 && model->active_notes[0] == st->base_note) {
        /* Chien volume and speed should not change until we get a notoff */
        return;
    }

    velocity = map_value(raw_chien_speed, &state->speed_to_percussion);

    mg_voice_clear_notes(model);
    note = mg_voice_enable_note(model, st->base_note);
    note->velocity = velocity;
}
