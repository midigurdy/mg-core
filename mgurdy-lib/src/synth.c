/**
 * This file contains all the modelling code that uses the sensor readings to
 * emulate a hurdy-gurdy.
 */

#include "synth.h"

#include "utils.h"
#include "state.h"


#define MG_WHEEL_EXPECTED_US (1100)
#define MG_WHEEL_START_SPEED (80)


static void debounce_keys(struct mg_keyboard *kb, const struct mg_key_calib key_calib[],
        int on_count, int off_count, int base_note_delay);
static void calc_wheel_speed(struct mg_wheel *wheel);



void mg_synth_update_sensors(struct mg_wheel *wheel, struct mg_keyboard *kb,
        const struct mg_state *state)
{
    debounce_keys(kb, state->key_calib,
            state->key_on_debounce, state->key_off_debounce,
            state->base_note_delay);

    calc_wheel_speed(wheel);
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
                else {
                    kb->active_keys[kb->active_key_count++] = i;
                }
            }
        }
    }

    if (kb->active_key_count == 0) {
        if (kb->inactive_count < base_note_delay) {
            kb->inactive_count++;
        }
    } else {
        kb->inactive_count = 0;
    }
}


