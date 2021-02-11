#include "model_fluid.h"

#include "server.h"
#include "utils.h"
#include "state.h"


static void melody_model_midigurdy(struct mg_voice *model, const struct mg_string *st,
        const struct mg_state *state, const struct mg_keyboard *kb,
        int expression, int velocity_switching);

static void melody_model_keyboard(struct mg_voice *model, const struct mg_string *st,
        const struct mg_state *state, const struct mg_keyboard *kb);

static void trompette_model_percussion(struct mg_voice *model,
        const struct mg_string *st, const struct mg_state *state,
        int wheel_speed);

static void trompette_model_midigurdy(struct mg_voice *model,
        const struct mg_string *st, const struct mg_state *state,
        int wheel_speed);


void model_fluid_update_melody_streams(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel, const struct mg_keyboard *kb)
{
    int i;

    struct mg_stream *stream;
    const struct mg_string *st;
    struct mg_voice *model;
    int expression = 0;

    /* Expression is the same for all melody strings, calculate here only once. */
    expression = map_value(wheel->speed, &state->speed_to_melody_volume);

    /* Update the model of all three melody streams */
    for (i = 0; i < 3; i++) {
        stream = output->stream[i];

        st = stream->string;
        model = &stream->model;

        /* If the string is muted, then there's no need to do anything */
        if (st->muted) {
            if (model->note_count > 0) {
                mg_voice_clear_notes(model);
            }
            continue;
        }

        model->volume = st->volume;
        model->panning = st->panning;
        model->bank = st->bank;
        model->program = st->program;

        if (model->mode != st->mode) {
            mg_voice_clear_notes(model);
            model->mode = st->mode;
        }

        if (st->mode == MG_MODE_MIDIGURDY) {
            // with velocity switching
            melody_model_midigurdy(model, st, state, kb, expression, 1);
        }
        else if (st->mode == MG_MODE_GENERIC) {
            // without velocity switching
            melody_model_midigurdy(model, st, state, kb, expression, 0);
        }
        else {
            melody_model_keyboard(model, st, state, kb);
        }
    }
}

void model_fluid_update_trompette_streams(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel)
{
    int i;

    struct mg_stream *stream;
    const struct mg_string *st;
    struct mg_voice *model;

    for (i = 3; i < 6; i++) {
        stream = output->stream[i];

        st = stream->string;
        model = &stream->model;

        /* If the string is muted, then there's no need to do any anything */
        if (st->muted) {
            if (model->note_count > 0) {
                mg_voice_clear_notes(model);
            }
            continue;
        }

        model->volume = st->volume;
        model->panning = st->panning;
        model->bank = st->bank;
        model->program = st->program;

        if (model->mode != st->mode) {
            mg_voice_clear_notes(model);
            model->mode = st->mode;
        }

        /* Standard modelling for MidiGurdy Soundfonts: trompette string sound
         * and chien sound are part of a single preset and mixed together,
         * their individual volumes controlled by channel pressure */
        if (st->mode == MG_MODE_MIDIGURDY) {
            trompette_model_midigurdy(model, st, state, wheel->speed);
        }

        /* Percussive mode, more suitable for other sounds like drums or other percussive sounds:
         * Only when the threshold is reached does a note-on occur, the velocity of the
         * note-on is calculated from the wheel speed above the threshold */
        else { // st->mode == MG_MODE_GENERIC
            trompette_model_percussion(model, st, state, wheel->speed);
        }
    }
}

void model_fluid_update_drone_streams(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel)
{
    int i;
    int expression;
    struct mg_stream *stream;
    const struct mg_string *st;
    struct mg_note *note;
    struct mg_voice *model;

    /* Expression is also the same for all drone strings, calculate here only once. */
    expression = map_value(wheel->speed, &state->speed_to_drone_volume);

    for (i = 6; i < 9; i++) {
        stream = output->stream[i];

        st = stream->string;
        model = &stream->model;

        if (st->muted) {
            model->expression = 0;
        } else {
            model->expression = expression;
        }

        if (model->expression <= 0) {
            if (model->note_count > 0) {
                mg_voice_clear_notes(model);
            }
            continue;
        }

        model->volume = st->volume;
        model->panning = st->panning;
        model->bank = st->bank;
        model->program = st->program;

        /* No change in base note, moving on... */
        if (model->note_count > 0 && model->active_notes[0] == st->base_note) {
            continue;
        }

        mg_voice_clear_notes(model);
        note = mg_voice_enable_note(model, st->base_note);
        note->velocity = 127;
    }
}

void model_fluid_update_keynoise_stream(struct mg_output *output,
        const struct mg_state *state, const struct mg_wheel *wheel, const struct mg_keyboard *kb)
{
    int i, key_num;
    const struct mg_key *key;
    int midi_note;
    int velocity;
    struct mg_note *note;

    struct mg_stream *stream = output->stream[9];
    const struct mg_string *st = stream->string;
    struct mg_voice *model = &stream->model;

    if (model->note_count > 0) {
        mg_voice_clear_notes(model);
    }

    if (st->muted) {
        return;
    }

    model->volume = st->volume;
    model->panning = st->panning;
    model->bank = st->bank;
    model->program = st->program;

    if (wheel->speed > 0) {
        model->pressure = 127;
    } else {
        model->pressure = 0;
    }

    for (i = 0; i < kb->changed_key_count; i++) {
        key_num = kb->changed_keys[i];
        key = &kb->keys[key_num];

        velocity = key->velocity;

        if (velocity < 0) {
            velocity = 0;
        }

        velocity = map_value(velocity, &state->keyvel_to_keynoise);

        if (velocity == 0) {
            continue;  // no need to send these...
        }

        /* Key on noise always uses the note range 60 - 83, key off noise 30 - 53 */
        if (key->action == KEY_PRESSED) {
            midi_note = 60 + key_num;
        }
        else {
            midi_note = 30 + key_num;
        }

        note = mg_voice_enable_note(model, midi_note);
        note->velocity = velocity;
    }
}


static void melody_model_midigurdy(struct mg_voice *model,
        const struct mg_string *st,
        const struct mg_state *state,
        const struct mg_keyboard *kb,
        int expression,
        int velocity_switching)
{
    struct mg_note *note;
    const struct mg_key *key;
    int key_idx;
    int key_num;
    int prev_expression = model->expression;

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

        if (velocity_switching) {
            /* Velocity switch based on the previous wheel speed */
            note->velocity = (prev_expression < MG_MELODY_EXPRESSION_THRESHOLD) ? 1 : 31;
        } else {
            note->velocity = 120;
        }

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

        if (velocity_switching) {
            /* Velocity switching:
            * If the key for the note we're enabling has recently been pressed,
            * then use the key velocity to determine the note velocity
            * (63 values, from 64 to 127).
            *
            * If the key for the note we're enabling was already pressed for longer,
            * then use the fixed velocity of 32.
            */
            if (key->active_since < state->base_note_delay) {
                note->velocity = 64 + map_value(key->velocity, &state->keyvel_to_tangent);
            } else {
                note->velocity = 32;
            }
        } else {
            note->velocity = 120;
        }

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

        /* If a base note delay is set, wait for that number of iterations before reacting */
        if (kb->inactive_count < state->base_note_delay) {
            return;
        }

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

static void trompette_model_midigurdy(struct mg_voice *model,
        const struct mg_string *st, const struct mg_state *state,
        int wheel_speed)
{
    struct mg_note *note;
    int chien_speed_factor;
    int normalized_chien_speed = 0;
    int raw_chien_speed = wheel_speed - st->threshold;

    if (raw_chien_speed > 0) {
        chien_speed_factor = map_value((5000 - st->threshold) / 50,
                &state->chien_threshold_to_range);

        if (chien_speed_factor > 0) {
            normalized_chien_speed = (raw_chien_speed * (chien_speed_factor + 100)) / 100;
        } else if (chien_speed_factor < 0) {
            normalized_chien_speed = (raw_chien_speed * -100) /  (chien_speed_factor - 100);
        } else {
            normalized_chien_speed = raw_chien_speed;
        }

        if (normalized_chien_speed > MG_CHIEN_MAX) {
            normalized_chien_speed = MG_CHIEN_MAX;
        }
    }

    if (normalized_chien_speed > 0) {
        model->pressure = map_value(normalized_chien_speed, &state->speed_to_chien);
    } else {
        model->pressure = 0;
    }

    model->expression = map_value(wheel_speed, &state->speed_to_trompette_volume);

    mg_server_record_chien_data(model->pressure, normalized_chien_speed);

    if (model->expression <= 0) {
        if (model->note_count > 0) {
            mg_voice_clear_notes(model);
        }
        return;
    }


    if (model->note_count > 0 && model->active_notes[0] == st->base_note) {
        return;
    }

    mg_voice_clear_notes(model);
    note = mg_voice_enable_note(model, st->base_note);
    note->velocity = 127; // volume controlled via expression
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
        mg_server_record_chien_data(0, 0);
        return;
    }

    if (model->note_count > 0 && model->active_notes[0] == st->base_note) {
        /* Chien volume and speed should not change until we get a notoff */
        mg_server_record_chien_data(-1, -1);
        return;
    }

    velocity = map_value(raw_chien_speed, &state->speed_to_percussion);

    mg_voice_clear_notes(model);
    note = mg_voice_enable_note(model, st->base_note);
    note->velocity = velocity;

    mg_server_record_chien_data(velocity, raw_chien_speed);
}
