/**
 * This file contains all the modelling code that uses the sensor readings to
 * emulate a hurdy-gurdy.
 */

#include "mg.h"
#include "synth.h"
#include "utils.h"
#include "state.h"


#define MG_WHEEL_EXPECTED_US (1100)
#define STOP_THRESHOLD (3)


static void debounce_keys(struct mg_core *mg, struct mg_key keys[], int on_count, int off_count);
static void calc_wheel_speed(struct mg_core *mg);
static void update_melody_model(struct mg_core *mg);
static void update_drone_model(struct mg_core *mg);
static void update_trompette_model(struct mg_core *mg);


/* Main entry point, called regularly by worker thread. Takes sensor readings
 * and updates the internal state of the instrument model.
 */
void mg_synth_update(struct mg_core *mg)
{
    debounce_keys(mg, mg->keys, mg->state.key_on_debounce, mg->state.key_off_debounce);
    debounce_keys(mg, mg->slow_keys, mg->state.key_on_debounce, mg->state.key_off_debounce);

    calc_wheel_speed(mg);

    update_melody_model(mg);
    update_trompette_model(mg);
    update_drone_model(mg);
}


/**
 * Calculate both speed and acceleration of the wheel.
 *
 * We do this on every core tick instead of on every wheel sensor reading,
 * because the wheel sensor kernel driver only reports if the angle has
 * actually changed.
 */
static void calc_wheel_speed(struct mg_core *mg)
{
    struct mg_wheel *wh = &mg->wheel;
    int dist = wh->distance;
    int speed;
    static int prev_speed = 0;
    static int stop_count = 0;

    if (wh->last_distance == 0) {
        if (stop_count < STOP_THRESHOLD) {
            stop_count++;
        }
    }
    else {
        stop_count = 0;
    }

    if (stop_count >= STOP_THRESHOLD) {
        speed = 0;
    }
    /* Ignore readings that have a very small or too long timeval. */
    else if (dist == 0 || (wh->elapsed_us < 500) || (wh->elapsed_us > 3000)) {
        speed = 0;
    }
    else {
        /* The wheel driver reports the travelled distance and the elapsed time since the last
         * reading. Normalize the speed to angle per millisecond, remove the directional information
         * (speed is always positive or 0) and increase the scale by 100 */
        if (dist < 0)
            dist *= -1;
        speed = (dist * 100 * MG_WHEEL_EXPECTED_US) / wh->elapsed_us;
    }

    if (speed > 0 || wh->speed > 0) {
        /* smooth the speed for a more realistic volume and attack response.
         * Acoustic strings are quite slow :-) */
        wh->speed = mg_smooth(speed, wh->speed, 0.8);
        wh->accel = wh->speed - prev_speed;
        prev_speed = wh->speed;
    }
    else {
        wh->speed = 0;
        wh->accel = 0;
        prev_speed = 0;
    }
}


static void debounce_keys(struct mg_core *mg, struct mg_key keys[], int on_count, int off_count)
{
    int i;
    struct mg_key *key;

    for (i=0; i < KEY_COUNT; i++) {
        key = &keys[i];

        key->action = 0;

        if (key->pressure > 0) {
            /* Key stays active */
            if (key->state == KEY_ACTIVE) {
                key->debounce = 0;
                if (key->active_since < mg->state.base_note_delay) {
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
                    /* Key on velocity is the maximum of all pressure values 
                     * seen during debounce period */
                    key->velocity = key->max_pressure * mg->key_calib[i].velocity_adjust;
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
                    /* Key off velocity is the last pressure value before
                     * going into inactive state */
                    key->velocity = key->smoothed_pressure * mg->key_calib[i].velocity_adjust;
                    key->max_pressure = 0;
                    key->smoothed_pressure = 0;
                    key->debounce = 0;
                }
            }
        }
    }
}


/**
 * Update all values in the melody models that depend on a sensor reading.
 */
static void update_melody_model(struct mg_core *mg)
{
    int i, s;

    int active_keys[KEY_COUNT + 1];
    int active_count = 0;

    int active_slow_keys[KEY_COUNT + 1];
    int active_slow_count = 0;

    int key_num = -1;

    struct mg_key *key;
    struct mg_string *st;
    struct mg_voice *model;
    struct mg_note *note;

    int base_note_delay = mg->state.base_note_delay;

    int midi_note;
    int expression = 0;

    static int prev_expression = 0;

    /* Find all currently active keys. */
    for (i = 0; i < KEY_COUNT; i++) {
        if (mg->keys[i].state == KEY_ACTIVE) {
            active_keys[active_count++] = i;
        }
        if (mg->slow_keys[i].state == KEY_ACTIVE) {
            active_slow_keys[active_slow_count++] = i;
        }
    }

    /* Expression is also the same for all melody strings, calculate here only once. */
    expression = multimap(mg->wheel.speed,
            mg->state.speed_to_melody_volume.ranges,
            mg->state.speed_to_melody_volume.count);

    /* Update the model of all three melody strings */
    for (s = 0; s < 3; s++) {
        st = &mg->state.melody[s];
        model = &st->model;

        /* If the string is muted, then there's no need to do any calculation. Just set
         * the volme to zero and go to next string. */
        if (st->muted || mg->halt_midi_output) {
            model->volume = 0;
            continue;
        }

        model->panning = st->panning;
        model->volume = st->volume;

        /* In keyboard mode, sound volume is controlled via velocity.
         * In all other modes, it is controlled via expression. */
        if (st->mode == MG_MODE_KEYBOARD) {
            model->expression = 127;
        }
        else {
            model->expression = expression;
        }

        /* In the non-polyphonic mode (the default), only the highest key creates
         * a note. If no key is pressed, or if the highest pressed key is below the
         * capo (empty_key), the string base_note note is playing */
        if (!st->polyphonic) {
            if (active_count && active_keys[active_count - 1] >= st->empty_key) {
                mg_string_clear_notes(st);
                st->base_note_count = 0;

                if (model->expression > 0) {
                    key_num = active_keys[active_count - 1];  // highest key number
                    key = &mg->keys[key_num];

                    midi_note = st->base_note + key_num + 1;
                    if (midi_note > 127) midi_note = 127;
                    model->active_notes[model->note_count++] = midi_note;

                    note = &model->notes[midi_note];
                    note->channel = st->channel;

                    if (st->mode == MG_MODE_GENERIC) {
                        note->velocity = 120;
                        note->pressure = 0;
                        model->pitch = 0x2000 + (
                                mg->state.pitchbend_factor *
                                multimap(key->smoothed_pressure,
                                    mg->state.pressure_to_pitch.ranges,
                                    mg->state.pressure_to_pitch.count));
                    }
                    else if (st->mode == MG_MODE_KEYBOARD) {
                        note->velocity = multimap(key->velocity,
                                mg->state.keyvel_to_notevel.ranges,
                                mg->state.keyvel_to_notevel.count);
                        note->pressure = 0;
                        model->pitch = 0x2000;  // no pitch bend in keyboard mode
                    }
                    else {  // MG_MODE_MIDIGURDY
                        /* If the key for the note we're enabling has recently been pressed,
                         * then use the key velocity to determine the note velocity
                         * (27 values,from 101 to 127).
                         *
                         * If the key for the note we're enabling was already pressed for longer,
                         * then use the velocity 100.
                         */
                        if (key->active_since < mg->state.base_note_delay) {
                            note->velocity = 64 + multimap(key->velocity,
                                    mg->state.keyvel_to_tangent.ranges,
                                    mg->state.keyvel_to_tangent.count);
                        } else {
                            note->velocity = 32;
                        }
                        /*
                        note->pressure = multimap(key->smoothed_pressure,
                                mg->state.pressure_to_poly.ranges,
                                mg->state.pressure_to_poly.count);
                        */
                        note->pressure = 0;
                        model->pitch = 0x2000 + (
                                mg->state.pitchbend_factor *
                                multimap(key->smoothed_pressure,
                                    mg->state.pressure_to_pitch.ranges,
                                    mg->state.pressure_to_pitch.count));
                    }
                }
            }
            /* Empty note if no key is pressed only in generic and midigurdy mode */
            else if (st->mode != MG_MODE_KEYBOARD) {
                if (st->base_note_count < base_note_delay) {
                    st->base_note_count++;
                }
                else {
                    mg_string_clear_notes(st);

                    /* Only sound base note if the wheel is moving */
                    if (model->expression > 0) {
                        midi_note = st->base_note + st->empty_key;
                        if (midi_note > 127) midi_note = 127;
                        note = &model->notes[midi_note];
                        note->channel = st->channel;
                        if (st->mode == MG_MODE_MIDIGURDY) {
                            if (prev_expression < MG_MELODY_EXPRESSION_THRESHOLD) {
                                note->velocity = 1;
                            }
                            else {
                                note->velocity = 32;
                            }
                        } else {
                            note->velocity = 64; // FIXME: is this a good default for generic?
                        }
                        note->pressure = 0; // no key, no pressure...
                        model->active_notes[model->note_count++] = midi_note;
                        model->pitch = 0x2000; // no key, no pitch bend!
                    }
                }
            }
            else {
                    mg_string_clear_notes(st);
            }
        }
        /* In polyphonic mode, multiple notes can play at the same time. Go
         * through all pressed keys and add all corresponding notes.
         * If no key is pressed, the string is quiet. */
        else {
            mg_string_clear_notes(st);

            for (i = 0; i < active_slow_count; i++) {
                key_num = active_slow_keys[i];
                key = &mg->slow_keys[key_num];

                midi_note = st->base_note + key_num + 1;
                if (midi_note > 127) midi_note = 127;
                model->active_notes[model->note_count++] = midi_note;

                note = &model->notes[midi_note];
                note->channel = st->channel;

                if (st->mode == MG_MODE_GENERIC) {
                    note->velocity = 120;
                    note->pressure = 0;
                }
                else if (st->mode == MG_MODE_KEYBOARD) {
                    note->velocity = multimap(key->velocity,
                            mg->state.keyvel_to_notevel.ranges,
                            mg->state.keyvel_to_notevel.count);
                    note->pressure = 0;
                }
                else { // MG_MODE_MIDIGURDY
                    note->velocity = 64 + multimap(key->velocity,
                            mg->state.keyvel_to_tangent.ranges,
                            mg->state.keyvel_to_tangent.count);
                    note->pressure = multimap(key->smoothed_pressure,
                            mg->state.pressure_to_poly.ranges,
                            mg->state.pressure_to_poly.count);
                }

                model->pitch = 0x2000;  // no pitch bend in polyphonic mode for now
            }
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
    int s, i;
    int expression;
    int midi_note;
    struct mg_string *st;
    struct mg_note *note;
    struct mg_voice *model;

    /* Expression is also the same for all drone strings, calculate here only once. */
    expression = multimap(mg->wheel.speed,
            mg->state.speed_to_drone_volume.ranges,
            mg->state.speed_to_drone_volume.count);

    for (s = 0; s < 3; s++) {
        st = &mg->state.drone[s];
        model = &st->model;

        model->panning = st->panning;

        /* If the string is muted, then there's no need to do any calculation. Just set
         * the volme to zero and go to next string. */
        if (st->muted || mg->halt_midi_output) {
            model->volume = 0;
            continue;
        }

        model->volume = st->volume;
        model->expression = expression;
        mg_string_clear_notes(st);

        if (expression <= 0)
            continue;

        for (i = 0; i < st->fixed_note_count; i++) {
            midi_note = st->fixed_notes[i];

            note = &model->notes[midi_note];
            note->channel = st->channel;
            note->velocity = 127;
            note->pressure = 0;
            model->active_notes[model->note_count++] = midi_note;
        }
    }
}

static void update_trompette_model(struct mg_core *mg)
{
    int s, i;
    int expression;
    int pressure;
    int midi_note;
    int chien_speed;
    int threshold;
    static int accel = 0;
    int normalized_speed;
    struct mg_string *st;
    struct mg_note *note;
    struct mg_voice *model;

    /* Expression is the same for all trompette strings, calculate here only once. */
    expression = multimap(mg->wheel.speed,
            mg->state.speed_to_trompette_volume.ranges,
            mg->state.speed_to_trompette_volume.count);

    /* Same with chien volume (channel pressure) for now. We only use the
     * threshold of the first string.
     *
     * To calculate the chien volume we first check if the wheel speed
     * is over the threshold. Then we normalize the range between threshold
     * and MAX_SPEED to 1000, which is then mapped to the proper value
     * using the speed_to_chien mapping.
     */
    pressure = 0;
    normalized_speed = 0;

    if (expression > 0) {  // no volume -> no trompette or chien :-)
        threshold = mg->state.trompette[0].threshold;
        chien_speed = mg->wheel.speed - threshold;
        if (chien_speed > 0) {
            if (threshold >= MG_SPEED_MAX) {
                pressure = 127;  // to avoid division by zero
                normalized_speed = 1000;
            }
            else {
                normalized_speed = (chien_speed * 1000) / (MG_SPEED_MAX - threshold);
                accel = mg->wheel.accel;
                if (accel > 0)
                    accel = mg_smooth(accel, accel, 0.8);
                else
                    accel = mg_smooth(0, accel, 0.8);
                normalized_speed += accel;
                pressure = multimap(normalized_speed,
                        mg->state.speed_to_chien.ranges,
                        mg->state.speed_to_chien.count);
            }
        }
    }

    mg->chien_volume = pressure;
    mg->chien_speed = normalized_speed;

    for (s = 0; s < 3; s++) {
        st = &mg->state.trompette[s];
        model = &st->model;

        model->panning = st->panning;

        /* If the string is muted, then there's no need to do any calculation. Just set
         * the volme to zero and go to next string. */
        if (st->muted || mg->halt_midi_output) {
            model->volume = 0;
            continue;
        }

        model->volume = st->volume;
        model->expression = expression;
        model->pressure = mg_smooth(pressure, model->pressure, 0.8);  // channel pressure
        mg_string_clear_notes(st);

        if (expression <= 0)
            continue;

        for (i = 0; i < st->fixed_note_count; i++) {
            midi_note = st->fixed_notes[i];

            note = &model->notes[midi_note];
            note->channel = st->channel;
            note->velocity = 127;
            note->pressure = 0;  // polyphonic pressure
            model->active_notes[model->note_count++] = midi_note;
        }
    }
}
