#include "mg.h"

#include "state.h"


static void reset_string(struct mg_string *string);


#define ENSURE_NOTE_RANGE(param) if (param < 0) param = 0; else if (param > 127) param = 127;

static struct mg_map default_pressure_to_pitch = {
    .count = 4,
    .ranges = {
        {0, -0x2000},
        {650, -280},
        {2400, 360},
        {MG_PRESSURE_MAX, 0x2000}
    }
};

static struct mg_map default_pressure_to_poly = {
    .count = 4,
    .ranges = {
        {0, 0}, {600, 100}, {1000, 120}, {MG_PRESSURE_MAX, 127}
    }
};

static struct mg_map default_speed_to_melody_volume = {
    .count = 6,
    .ranges = {
        {0, 0}, {430, 35}, {900, 60}, {1400, 75}, {2000, 87}, {5000, 127},
    }
};

static struct mg_map default_speed_to_drone_volume = {
    .count = 6,
    .ranges = {
        {0, 0}, {430, 35}, {900, 60}, {1400, 75}, {2000, 87}, {5000, 127},
    }
};

static struct mg_map default_speed_to_trompette_volume = {
    .count = 6,
    .ranges = {
        {0, 0}, {430, 35}, {900, 60}, {1400, 75}, {2000, 87}, {5000, 127},
    }
};

static struct mg_map default_speed_to_chien = {
    .count = 4,
    .ranges = {
        {0, 0}, {400, 80}, {1000, 120}, {4000, 127}
    }
};

static struct mg_map default_chien_threshold_to_range = {
    .count = 3,
    .ranges = {
        {0, 50}, {50, 0}, {100, -50},
    }
};

static struct mg_map default_speed_to_percussion = {
    .count = 4,
    .ranges = {
        {0, 70}, {200, 100}, {500, 120}, {1000, 127}
    }
};

static struct mg_map default_keyvel_to_notevel = {
    .count = 2,
    .ranges = {
        {0, 20}, {MG_KEYVEL_MAX, 127}
    }
};

static struct mg_map default_keyvel_to_tangent = {
    .count = 2,
    .ranges = {
        {0, 0}, {MG_KEYVEL_MAX, 63}
    }
};

static struct mg_map default_keyvel_to_keynoise = {
    .count = 2,
    .ranges = {
        {0, 0}, {MG_KEYVEL_MAX, 127}
    }
};


/**
 * Sets all state fields, structs and lists to their initial values
 */
int mg_state_init(struct mg_state *state)
{
    int i;

    for (i = 0; i < 3; i++) {
        reset_string(&state->melody[i]);
        reset_string(&state->drone[i]);
        reset_string(&state->trompette[i]);
    }
    reset_string(&state->keynoise);

    state->pitchbend_factor = 0.5; // 100 cents of default bend range

    state->key_on_debounce = 2;
    state->key_off_debounce = 10;
    state->base_note_delay = 20;

    state->poly_base_note = 1; // default on
    state->poly_pitch_bend = 1; // default on

    mg_reset_mapping_ranges(MG_MAP_PRESSURE_TO_PITCH);
    mg_reset_mapping_ranges(MG_MAP_PRESSURE_TO_POLY);
    mg_reset_mapping_ranges(MG_MAP_SPEED_TO_MELODY_VOLUME);
    mg_reset_mapping_ranges(MG_MAP_SPEED_TO_DRONE_VOLUME);
    mg_reset_mapping_ranges(MG_MAP_SPEED_TO_TROMPETTE_VOLUME);
    mg_reset_mapping_ranges(MG_MAP_SPEED_TO_CHIEN);
    mg_reset_mapping_ranges(MG_MAP_CHIEN_THRESHOLD_TO_RANGE);
    mg_reset_mapping_ranges(MG_MAP_SPEED_TO_PERCUSSION);
    mg_reset_mapping_ranges(MG_MAP_KEYVEL_TO_NOTEVEL);
    mg_reset_mapping_ranges(MG_MAP_KEYVEL_TO_TANGENT);
    mg_reset_mapping_ranges(MG_MAP_KEYVEL_TO_KEYNOISE);

    /* Set initial key calibration values */
    for (i = 0; i < KEY_COUNT; i++) {
        state->key_calib[i].pressure_adjust = 1.0f;
        state->key_calib[i].velocity_adjust = 1.0f;
    }
    
    return 0;
}


int mg_state_lock(struct mg_state *state)
{
    int err;

    err = pthread_mutex_lock(&state->mutex);
    if (err)
        perror("Unable to aquire state mutex");

    return err;
}


int mg_state_unlock(struct mg_state *state)
{
    int err;

    err = pthread_mutex_unlock(&state->mutex);
    if (err)
        perror("Unable to release mg_core mutex");

    return err;
}


/**
 * Mute or unmute a string
 */
void mg_string_set_mute(struct mg_string *st, int muted)
{
    st->muted = muted;
}


void mg_string_set_volume(struct mg_string *st, int volume)
{
    ENSURE_NOTE_RANGE(volume);

    st->volume = volume;
}


/**
 * This has only effect on the melody string. Drone and trompette get
 * their notes set directly.
 */
void mg_string_set_base_note(struct mg_string *st, int base_note)
{
    ENSURE_NOTE_RANGE(base_note);

    st->base_note = base_note;
}


/**
 * This only has an effect on trompette strings.
 */
void mg_string_set_chien_threshold(struct mg_string *st, int threshold)
{
    st->threshold = MIN(threshold, MG_SPEED_MAX - 1);
}


/**
 * Removes all active notes from a voice.
 */
void mg_voice_clear_notes(struct mg_voice *voice)
{
    int i;

    for (i = 0; i < voice->note_count; i++) {
        voice->notes[voice->active_notes[i]].on = 0;
    }
    voice->note_count = 0;
}


struct mg_map *mg_state_get_mapping(struct mg_state *state, int idx)
{
    switch(idx) {
        case MG_MAP_PRESSURE_TO_POLY:
            return &state->pressure_to_poly;
        case MG_MAP_PRESSURE_TO_PITCH:
            return &state->pressure_to_pitch;
        case MG_MAP_SPEED_TO_MELODY_VOLUME:
            return &state->speed_to_melody_volume;
        case MG_MAP_SPEED_TO_DRONE_VOLUME:
            return &state->speed_to_drone_volume;
        case MG_MAP_SPEED_TO_TROMPETTE_VOLUME:
            return &state->speed_to_trompette_volume;
        case MG_MAP_SPEED_TO_CHIEN:
            return &state->speed_to_chien;
        case MG_MAP_CHIEN_THRESHOLD_TO_RANGE:
            return &state->chien_threshold_to_range;
        case MG_MAP_SPEED_TO_PERCUSSION:
            return &state->speed_to_percussion;
        case MG_MAP_KEYVEL_TO_NOTEVEL:
            return &state->keyvel_to_notevel;
        case MG_MAP_KEYVEL_TO_TANGENT:
            return &state->keyvel_to_tangent;
        case MG_MAP_KEYVEL_TO_KEYNOISE:
            return &state->keyvel_to_keynoise;
        default:
            fprintf(stderr, "Invalid mapping index: %d\n", idx);
            return NULL;
    }
}


struct mg_map *mg_state_get_default_mapping(int idx)
{
    switch(idx) {
        case MG_MAP_PRESSURE_TO_POLY:
            return &default_pressure_to_poly;
        case MG_MAP_PRESSURE_TO_PITCH:
            return &default_pressure_to_pitch;
        case MG_MAP_SPEED_TO_MELODY_VOLUME:
            return &default_speed_to_melody_volume;
        case MG_MAP_SPEED_TO_DRONE_VOLUME:
            return &default_speed_to_drone_volume;
        case MG_MAP_SPEED_TO_TROMPETTE_VOLUME:
            return &default_speed_to_trompette_volume;
        case MG_MAP_SPEED_TO_CHIEN:
            return &default_speed_to_chien;
        case MG_MAP_CHIEN_THRESHOLD_TO_RANGE:
            return &default_chien_threshold_to_range;
        case MG_MAP_SPEED_TO_PERCUSSION:
            return &default_speed_to_percussion;
        case MG_MAP_KEYVEL_TO_NOTEVEL:
            return &default_keyvel_to_notevel;
        case MG_MAP_KEYVEL_TO_TANGENT:
            return &default_keyvel_to_tangent;
        case MG_MAP_KEYVEL_TO_KEYNOISE:
            return &default_keyvel_to_keynoise;
        default:
            fprintf(stderr, "Invalid mapping index: %d\n", idx);
            return NULL;
    }
}


static void reset_string(struct mg_string *string)
{
    string->base_note = 60;  // middle C
    string->muted = 1; // default is off
    string->volume = 127; // max volume
    string->panning = 64;  // center
    string->bank = 0;
    string->program = 0;

    string->mode = MG_MODE_MIDIGURDY;

    string->polyphonic = 0; // normal mode
    string->empty_key = 0;  // open string

    string->threshold = 0;

    mg_state_reset_model_voice(&string->model);
}


void mg_state_reset_model_voice(struct mg_voice *voice)
{
    int i;

    voice->expression = 127;
    voice->pitch = 0x2000;
    voice->volume = 127;
    voice->panning = 64;
    voice->pressure = 0;
    voice->bank = 0;
    voice->program = 0;
    voice->mode = -1;

    voice->chien_on_debounce = 2;
    voice->chien_off_debounce = 3;
    voice->chien_debounce = 0;

    for (i = 0; i < NUM_NOTES; i++) {
        voice->notes[i].on = 0;
        voice->notes[i].velocity = 0;
        voice->notes[i].pressure = 0;
    }
    voice->note_count = 0;
}


void mg_state_reset_output_voice(struct mg_voice *voice)
{
    int i;

    voice->expression = -1;
    voice->pitch = -1;
    voice->volume = -1;
    voice->panning = -1;
    voice->pressure = -1;
    voice->bank = -1;
    voice->program = 1;
    voice->mode = -1;

    for (i = 0; i < NUM_NOTES; i++) {
        voice->notes[i].on = 0;
        voice->notes[i].velocity = 0;
        voice->notes[i].pressure = 0;
    }
    voice->note_count = 0;
}
