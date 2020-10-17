/**
 * This file contains all the modelling code that uses the sensor readings to
 * emulate a hurdy-gurdy.
 */

#include "mg.h"
#include "synth.h"
#include "utils.h"
#include "state.h"


#define MG_WHEEL_EXPECTED_US (1100)
#define MG_WHEEL_START_SPEED (80)


static void debounce_keys(struct mg_keyboard *kb, const struct mg_key_calib key_calib[],
        int on_count, int off_count, int base_note_delay);
static void calc_wheel_speed(struct mg_wheel *wheel);

static void update_melody_model(struct mg_core *mg);
static void melody_model_midigurdy(struct mg_core *mg, struct mg_string *st,
        const struct mg_keyboard *kb,
        int expression, int prev_expression,
        int velocity_switching);
static void melody_model_keyboard(struct mg_core *mg, struct mg_string *st,
        const struct mg_keyboard *kb);

static void update_trompette_model(struct mg_core *mg);
static void trompette_model_percussion(const struct mg_state *state,
        struct mg_string *st, int raw_chien_speed, int *ws_chien_speed, int *ws_chien_volume);
static void trompette_model_midigurdy(const struct mg_state *state,
        struct mg_string *st, int normalized_chien_speed, int wheel_speed,
        int *ws_chien_speed, int *ws_chien_volume);

static void update_drone_model(struct mg_core *mg);
static void update_keynoise_model(struct mg_core *mg);

static struct mg_note *enable_voice_note(struct mg_voice *voice, int midi_note);

/* Main entry point, called regularly by worker thread. Takes sensor readings
 * and updates the internal state of the instrument model.
 */
void mg_synth_update(struct mg_core *mg)
{
    struct mg_keyboard *kb = &mg->keyboard;
    struct mg_wheel *wheel = &mg->wheel;
    struct mg_state *state = &mg->state;

    debounce_keys(kb, state->key_calib,
            state->key_on_debounce, state->key_off_debounce,
            state->base_note_delay);

    calc_wheel_speed(wheel);

    if (wheel->speed == 0) {
        kb->inactive_count = state->base_note_delay;
    }
    else if (kb->active_key_count == 0) {
        if (kb->inactive_count < state->base_note_delay) {
            kb->inactive_count++;
        }
    } else {
        kb->inactive_count = 0;
    }

    update_melody_model(mg);
    update_trompette_model(mg);
    update_drone_model(mg);
    update_keynoise_model(mg);
}


/**
 * Calculate speed of the wheel and related parameters.
 *
 * We do this on every core tick instead of on every wheel sensor reading,
 * because the wheel sensor kernel driver only reports if the angle has
 * actually changed.
 */
static void calc_wheel_speed(struct mg_wheel *wheel)
{
    int speed;

    /* Ignore readings that have a very small or too long timeval. */
    if ((wheel->elapsed_us < 500) || (wheel->elapsed_us > 3000)) {
        return;
    }

    /* The wheel driver reports the travelled distance and the elapsed time since the last
        * reading. Normalize the speed to angle per tick (millisecond),
        * remove the directional information
        * (speed is always positive or 0) and increase the scale by 100 */
    speed = (wheel->distance * (wheel->distance < 0 ? -100 : 100) * MG_WHEEL_EXPECTED_US) / wheel->elapsed_us;

    if (speed > 0 || wheel->raw_speed > 0) {
        /* smooth the speed for a more realistic volume and attack response.
         * Acoustic strings are quite slow :-) */
        wheel->raw_speed = mg_smooth(speed, wheel->raw_speed, 0.8);
    }

    if (wheel->speed || wheel->raw_speed >= MG_WHEEL_START_SPEED) {
        wheel->speed = wheel->raw_speed;
    } else {
        wheel->speed = 0;
    }
}


static void debounce_keys(struct mg_keyboard *kb, const struct mg_key_calib key_calib[],
        int on_count, int off_count, int base_note_delay)
{
    int i;
    struct mg_key *key;

    kb->active_key_count = 0;
    kb->changed_key_count = 0;

    for (i=0; i < KEY_COUNT; i++) {
        key = &kb->keys[i];

        key->action = 0;

        if (key->pressure > 0) {
            /* Key stays active */
            if (key->state == KEY_ACTIVE) {
                kb->active_keys[kb->active_key_count++] = i;
                key->debounce = 0;
                if (key->active_since < base_note_delay) {
                    key->active_since++;
                }
            }
            else {
                key->debounce++;

                /* Key becomes active */
                if (key->debounce > on_count) {
                    key->state = KEY_ACTIVE;
                    key->action = KEY_PRESSED;
                    key->active_since = 0;

                    kb->changed_keys[kb->changed_key_count++] = i;
                    kb->active_keys[kb->active_key_count++] = i;

                    /* Key on velocity is the maximum of all pressure values 
                     * seen during debounce period */
                    key->velocity = key->max_pressure * key_calib[i].velocity_adjust;
                    key->debounce = 0;
                }
            }
        }
        else {
            /* Key stays inactive */
            if (key->state == KEY_INACTIVE) {
                key->debounce = 0;
            }
            else {
                key->debounce++;

                /* Key becomes inactive */
                if (key->debounce > off_count) {
                    key->state = KEY_INACTIVE;
                    key->action = KEY_RELEASED;
                    key->active_since = 0;

                    kb->changed_keys[kb->changed_key_count++] = i;

                    /* Key off velocity is the last pressure value before
                     * going into inactive state */
                    key->velocity = key->smoothed_pressure * key_calib[i].velocity_adjust;
                    key->max_pressure = 0;
                    key->smoothed_pressure = 0;
                    key->debounce = 0;
                }
            }
        }
    }

}


static void melody_model_midigurdy(struct mg_core *mg, struct mg_string *st,
        const struct mg_keyboard *kb,
        int expression, int prev_expression,
        int velocity_switching)
{
    struct mg_voice *model = &st->model;
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
        if (kb->inactive_count < mg->state.base_note_delay) {
            return;
        }

        mg_voice_clear_notes(model);

        /* No base note in polyphonic mode unless enabled */
        if (st->polyphonic && !mg->state.poly_base_note) {
            return;
        }

        /* Determine base note MIDI number, taking capo into account */
        note = enable_voice_note(model, st->base_note + st->empty_key);

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

    if (st->polyphonic && !mg->state.poly_pitch_bend) {
        model->pitch = 0x2000;
    } else {
        model->pitch = 0x2000 + (
            mg->state.pitchbend_factor *
            map_value(key->smoothed_pressure, &mg->state.pressure_to_pitch)
        );
    }

    /* Now go though all pressed keys in reverse order and set up the
     * corresponding notes. In monophonic mode, we do this only once for
     * the highest key. */
    do {
        key_num = kb->active_keys[key_idx];
        key = &kb->keys[key_num];

        note = enable_voice_note(model, st->base_note + key_num + 1);

        if (velocity_switching) {
            /* Velocity switching:
            * If the key for the note we're enabling has recently been pressed,
            * then use the key velocity to determine the note velocity
            * (63 values, from 64 to 127).
            *
            * If the key for the note we're enabling was already pressed for longer,
            * then use the fixed velocity of 32.
            */
            if (key->active_since < mg->state.base_note_delay) {
                note->velocity = 64 + map_value(key->velocity, &mg->state.keyvel_to_tangent);
            } else {
                note->velocity = 32;
            }
        } else {
            note->velocity = 120;
        }

        key_idx--;

    } while (key_idx >= 0 && st->polyphonic);
}


static void melody_model_keyboard(struct mg_core *mg, struct mg_string *st,
        const struct mg_keyboard *kb)
{
    struct mg_voice *model = &st->model;
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

        note = enable_voice_note(model, st->base_note + key_num + 1);

        /* ...and configure note parameters */
        note->velocity = map_value(key->velocity, &mg->state.keyvel_to_notevel);

        key_idx--;

    } while (key_idx >= 0 && st->polyphonic);
}

/**
 * Update all values in the melody models that depend on a sensor reading.
 */
static void update_melody_model(struct mg_core *mg)
{
    int s;

    struct mg_string *st;
    struct mg_voice *model;
    int expression = 0;

    static int prev_expression = 0;

    /* Expression is the same for all melody strings, calculate here only once. */
    expression = map_value(mg->wheel.speed, &mg->state.speed_to_melody_volume);

    /* Update the model of all three melody strings */
    for (s = 0; s < 3; s++) {
        st = &mg->state.melody[s];
        model = &st->model;

        /* If the string is muted, then there's no need to do anything */
        if (st->muted) {
            if (model->note_count > 0) {
                mg_voice_clear_notes(model);
            }
            continue;
        }

        if (model->mode != st->mode) {
            mg_voice_clear_notes(model);
            model->mode = st->mode;
        }

        if (st->mode == MG_MODE_MIDIGURDY) {
            // with velocity switching
            melody_model_midigurdy(mg, st, &mg->keyboard, expression, prev_expression, 1);
        }
        else if (st->mode == MG_MODE_GENERIC) {
            // without velocity switching
            melody_model_midigurdy(mg, st, &mg->keyboard, expression, prev_expression, 0);
        }
        else {
            melody_model_keyboard(mg, st, &mg->keyboard);
        }
    }

    prev_expression = expression;
}


/**
 * Update all drone strings. This is fairly simple, as note changes to the 
 * model come from the Python program and are set directly on the model.
 *
 * Only need to calculate the expression.
 */
static void update_drone_model(struct mg_core *mg)
{
    int s;
    int expression;
    struct mg_string *st;
    struct mg_note *note;
    struct mg_voice *model;

    /* Expression is also the same for all drone strings, calculate here only once. */
    expression = map_value(mg->wheel.speed, &mg->state.speed_to_drone_volume);

    for (s = 0; s < 3; s++) {
        st = &mg->state.drone[s];
        model = &st->model;

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

        /* No change in base note, moving on... */
        if (model->note_count > 0 && model->active_notes[0] == st->base_note) {
            continue;
        }

        mg_voice_clear_notes(model);
        note = enable_voice_note(model, st->base_note);
        note->velocity = 127;
    }
}

static void update_trompette_model(struct mg_core *mg)
{
    int s;

    struct mg_string *st;
    struct mg_voice *model;

    int ws_chien_volume = -1;
    int ws_chien_speed = -1;

    int chien_speed_factor;
    int raw_chien_speed;
    int normalized_chien_speed = 0;

    for (s = 0; s < 3; s++) {
        st = &mg->state.trompette[s];
        model = &st->model;

        /* If the string is muted, then there's no need to do any anything */
        if (st->muted) {
            if (model->note_count > 0) {
                mg_voice_clear_notes(model);
            }
            continue;
        }

        if (st->threshold < MG_SPEED_MAX) {
            chien_speed_factor = map_value(
                    (5000 - st->threshold) / 50,
                    &mg->state.chien_threshold_to_range);
            raw_chien_speed = mg->wheel.speed - st->threshold;
            if (raw_chien_speed > 0) {
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
            else {
                raw_chien_speed = 0;
                normalized_chien_speed = 0;
            }
        } else {
            raw_chien_speed = 0;
            normalized_chien_speed = 0;
        }

        if (model->mode != st->mode) {
            mg_voice_clear_notes(model);
            model->mode = st->mode;
        }

        /* Standard modelling for MidiGurdy Soundfonts: trompette string sound
         * and chien sound are part of a single preset and mixed together,
         * their individual volumes controlled by channel pressure */
        if (st->mode == MG_MODE_MIDIGURDY) {
            trompette_model_midigurdy(&mg->state, st, normalized_chien_speed, mg->wheel.speed,
                    &ws_chien_speed, &ws_chien_volume);
        }

        /* Percussive mode, more suitable for other sounds like drums or other percussive sounds:
         * Only when the threshold is reached does a note-on occur, the velocity of the
         * note-on is calculated from the wheel speed above the threshold */
        else { // st->mode == MG_MODE_GENERIC
            trompette_model_percussion(&mg->state, st, raw_chien_speed,
                    &ws_chien_speed, &ws_chien_volume);
        }
    }

    /* Record the wheel speed and chien volume, so we can send it via websockets
     * to the visualisations */
    if (ws_chien_speed >= 0) {
        mg->chien_speed = ws_chien_speed;
    } else if (ws_chien_speed == -1) {
        mg->chien_speed = 0;
    }
    /* otherwise (-2) leave chien_speed unchanged */

    if (ws_chien_volume != -1) {
        mg->chien_volume = ws_chien_volume;
    }
}


static void trompette_model_midigurdy(const struct mg_state *state,
        struct mg_string *st, int normalized_chien_speed, int wheel_speed,
        int *ws_chien_speed, int *ws_chien_volume)
{
    struct mg_voice *model = &st->model;
    struct mg_note *note;

    if (normalized_chien_speed > 0) {
        model->pressure = map_value(normalized_chien_speed, &state->speed_to_chien);
    } else {
        model->pressure = 0;
    }

    model->expression = map_value(wheel_speed, &state->speed_to_trompette_volume);

    /* The first enabled trompette string (regardless of mode) determines
     * the chien volume we report to the visualizations via websocket */
    if (*ws_chien_volume == -1) {
        *ws_chien_volume = model->pressure;
    }

    if (*ws_chien_speed == -1) {
        *ws_chien_speed = normalized_chien_speed;
    }

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
    note = enable_voice_note(model, st->base_note);
    note->velocity = 127; // volume controlled via expression
}


static void trompette_model_percussion(const struct mg_state *state,
        struct mg_string *st, int raw_chien_speed, int *ws_chien_speed, int *ws_chien_volume)
{
    struct mg_voice *model = &st->model;
    int velocity;
    struct mg_note *note;

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
            if (*ws_chien_volume == -1) {
                *ws_chien_volume = 0;
            }
            if (*ws_chien_speed == -1) {
                *ws_chien_speed = 0;
            }
            mg_voice_clear_notes(model);
        }
        return;
    }

    if (model->note_count > 0 && model->active_notes[0] == st->base_note) {
        /* Set to -2 so that the speed reported via websockets does
         * not change until we get a noteoff */
        *ws_chien_speed = -2;
        return;
    }

    velocity = map_value(raw_chien_speed, &state->speed_to_percussion);

    if (*ws_chien_volume == -1) {
        *ws_chien_volume = velocity;
    }

    if (*ws_chien_speed == -1) {
        *ws_chien_speed = raw_chien_speed;
    }

    mg_voice_clear_notes(model);
    note = enable_voice_note(model, st->base_note);
    note->velocity = velocity;
}


static void update_keynoise_model(struct mg_core *mg)
{
    int i, key_idx;
    struct mg_key *key;
    int midi_note;
    int velocity;
    struct mg_string *st = &mg->state.keynoise;
    struct mg_keyboard *kb = &mg->keyboard;
    struct mg_voice *model = &st->model;
    struct mg_note *note;

    if (model->note_count > 0) {
        mg_voice_clear_notes(model);
    }

    if (st->muted) {
        return;
    }

    if (mg->wheel.speed > 0) {
        model->pressure = 127;
    } else {
        model->pressure = 0;
    }

    for (i = 0; i < kb->changed_key_count; i++) {
        key_idx = kb->changed_keys[i];
        key = &kb->keys[key_idx];

        velocity = key->velocity;

        if (velocity < 0) {
            velocity = 0;
        }

        velocity = map_value(velocity, &mg->state.keyvel_to_keynoise);

        if (velocity == 0)
            continue;  // no need to send these...

        /* Key on noise always uses the note range 60 - 83, key off noise 30 - 53 */
        if (key->action == KEY_PRESSED)
            midi_note = 60 + i;
        else
            midi_note = 30 + i;

        note = enable_voice_note(model, midi_note);
        note->velocity = velocity;
    }
}

static struct mg_note *enable_voice_note(struct mg_voice *voice, int midi_note) {
    struct mg_note *note;

    if (midi_note > 127) midi_note = 127;

    voice->active_notes[voice->note_count++] = midi_note;
    note = &voice->notes[midi_note];
    note->on = 1;

    return note;
}
