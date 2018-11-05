/**
 * Contains all functions to update the internal synth with the current
 * MidiGurdy state.
 */

#include "mg.h"
#include "utils.h"

#include "midi.h"
#include "midi_lowlevel.h"
#include "state.h"


static void sync_melody_voice(struct mg_core *mg, struct mg_string *st);
static void sync_drone_voice(struct mg_core *mg, struct mg_string *st);
static void sync_trompette_voice(struct mg_core *mg, struct mg_string *st);
static void sync_melody_keynoise_notes(struct mg_core *mg);
static void sync_notes(struct mg_core *mg, struct mg_voice *model, struct mg_output *out, int with_poly);


/* used to set if sync_notes should send Poly Pressure messages */
#define WITHOUT_POLY_PRESSURE (0)
#define WITH_POLY_PRESSURE (1)

#define MIDI_LSB(val) (val & 0x7F)
#define MIDI_MSB(val) ((val & (0x7F << 7)) >> 7)


/*
 * Synchronize the state of all voices with the internal synthesizer
 */
void mg_midi_sync(struct mg_core *mg)
{
    int i;

    /* Send note on / offs for the two key noise effect channels. Do this
     * first, as those sounds are *very* sensitive to latency */
    sync_melody_keynoise_notes(mg);

    for (i = 0; i < 3; i++)
        sync_melody_voice(mg, &mg->state.melody[i]);

    for (i = 0; i < 3; i++)
        sync_drone_voice(mg, &mg->state.drone[i]);

    for (i = 0; i < 3; i++)
        sync_trompette_voice(mg, &mg->state.trompette[i]);
}


/**
 * Update a melody voice.
 *
 * Melody voices send the common Note On/Off, Panning, Expression and Volume
 * messages, but also Pitch Bend and Poly Pressure (via sync_notes).
 */
static void sync_melody_voice(struct mg_core *mg, struct mg_string *st)
{
    struct mg_voice *model = &st->model;
    struct mg_output *out = &st->outputs[MG_OUTPUT_FLUID];

    if ((model->volume == 0 && out->voice.volume == 0)) {
        return;
    }
        
    /* Setup all sound characteristics before sending note on / off events. */
    if (model->expression || out->voice.expression) {
        if (out->voice.pitch != model->pitch) {
            mg_midi_pitch_bend(mg, st->channel, model->pitch);
            out->voice.pitch = model->pitch;
        }

        if (out->voice.panning != model->panning) {
            mg_midi_cc(mg, st->channel, MG_CC_PANNING, model->panning);
            out->voice.panning = model->panning;
        }
    }

    if (model->note_count || out->voice.note_count) {
        sync_notes(mg, model, out, WITH_POLY_PRESSURE);
    }

    if (out->voice.expression != model->expression) {
        mg_midi_cc(mg, st->channel, MG_CC_EXPRESSION, model->expression);
        out->voice.expression = model->expression;
    }

    if (out->voice.volume != model->volume) {
        mg_midi_cc(mg, st->channel, MG_CC_VOLUME, model->volume);
        out->voice.volume = model->volume;
    }
}


/**
 * Update a drone voice.
 *
 * Drone voices only send the common Note On/Off, Panning, Expression and
 * Volume messages.
 */
static void sync_drone_voice(struct mg_core *mg, struct mg_string *st)
{
    struct mg_voice *model = &st->model;
    struct mg_output *out = &st->outputs[MG_OUTPUT_FLUID];

    /* If the string can't be heard, then don't do anything. */
    if ((model->volume == 0 && out->voice.volume == 0)) {
        return;
    }
    
    if (model->expression || out->voice.expression) {
        if (out->voice.panning != model->panning) {
            mg_midi_cc(mg, st->channel, MG_CC_PANNING, model->panning);
            out->voice.panning = model->panning;
        }
    }

    if (model->note_count || out->voice.note_count) {
        sync_notes(mg, model, out, WITHOUT_POLY_PRESSURE);
    }

    if (out->voice.expression != model->expression) {
        mg_midi_cc(mg, st->channel, MG_CC_EXPRESSION, model->expression);
        out->voice.expression = model->expression;
    }

    if (out->voice.volume != model->volume) {
        mg_midi_cc(mg, st->channel, MG_CC_VOLUME, model->volume);
        out->voice.volume = model->volume;
    }
}


/**
 * Update a trompette voice.
 *
 * Trompette voices send the common Note On/Off, Panning, Expression and Volume
 * messages, but also Channel Pressure.
 */
static void sync_trompette_voice(struct mg_core *mg, struct mg_string *st)
{
    struct mg_voice *model = &st->model;
    struct mg_output *out = &st->outputs[MG_OUTPUT_FLUID];

    /* If the string can't be heard, then don't do anything. */
    if ((model->volume == 0 && out->voice.volume == 0)) {
        return;
    }
    
    if (model->expression || out->voice.expression) {
        if (out->voice.panning != model->panning) {
            mg_midi_cc(mg, st->channel, MG_CC_PANNING, model->panning);
            out->voice.panning = model->panning;
        }

        if (out->voice.pressure != model->pressure) {
            mg_midi_channel_pressure(mg, st->channel, model->pressure);
            out->voice.pressure = model->pressure;
        }
    }

    if (model->note_count || out->voice.note_count) {
        sync_notes(mg, model, out, WITHOUT_POLY_PRESSURE);
    }

    if (out->voice.expression != model->expression) {
        mg_midi_cc(mg, st->channel, MG_CC_EXPRESSION, model->expression);
        out->voice.expression = model->expression;
    }

    if (out->voice.volume != model->volume) {
        mg_midi_cc(mg, st->channel, MG_CC_VOLUME, model->volume);
        out->voice.volume = model->volume;
    }
}

/**
 * Update the key noise channels. This sync is special, beause it doesn't sync
 * with the string models but reads the key state directly.
 */
static void sync_melody_keynoise_notes(struct mg_core *mg)
{
    int i;
    struct mg_key *key;
    int midi_note;
    int velocity;

    for (i = 0; i < KEY_COUNT; i++) {
        key = &mg->keys[i];

        if (!key->action)
            continue;

        velocity = key->velocity;

        if (velocity < 0) {
            velocity = 0;
        }
        
        velocity = multimap(velocity,
                mg->state.keyvel_to_keynoise.ranges,
                mg->state.keyvel_to_keynoise.count);

        if (velocity == 0)
            continue;  // no need to send these...

        /* Key on noise always uses the note range 60 - 83, key off noise 30 - 53 */
        if (key->action == KEY_PRESSED)
            midi_note = 60 + i;
        else
            midi_note = 30 + i;

        /* No need for note off messages here, as key noises are not supposed to loop */
        mg_midi_noteon(mg, MG_KEYNOISE_CHANNEL, midi_note, velocity);
    }
}


/**
 * Update all notes for this voice. Sends Note On/Off and optionally also Poly Pressure
 * messages (only enabled for melody voices).
 */
static void sync_notes(struct mg_core *mg, struct mg_voice *model, struct mg_output *out, int with_poly)
{
    int i, key;
    struct mg_note *model_note;
    struct mg_note *out_note;

    int active_notes[NUM_NOTES];
    int note_count = 0;

    int notes_have_changed = 0;

    /* Handle new or currently sounding notes first as they are most timing critical. */
    for (i = 0; i < model->note_count; i++) {
        key = model->active_notes[i];
        model_note = &model->notes[key];
        out_note = &out->voice.notes[key];

        /* Send key pressure changes before note on, as it could affect the
         * sound of the note onset. */
        if (with_poly && (model_note->pressure != out_note->pressure)) {
            mg_midi_key_pressure(mg, model_note->channel, key, model_note->pressure);
            out_note->pressure = model_note->pressure;
        }

        /* Note on or channel switch.
         *
         * The MidGurdy doesn't change the velocity of already sounding
         * notes, so velocity is ignored here.
         */
        if (model_note->channel != out_note->channel) {
            mg_midi_noteon(mg, model_note->channel, key, model_note->velocity);

            /* If we're switching channels, then make sure all old notes are quiet. */
            if (out_note->channel != -1) {
                mg_midi_all_notes_off(mg, out_note->channel);
            }

            out_note->channel = model_note->channel;
            active_notes[note_count++] = key;
            notes_have_changed = 1;
        }
    }

    /* Then handle note off events. */
    for (i = 0; i < out->voice.note_count; i++) {
        key = out->voice.active_notes[i];
        model_note = &model->notes[key];
        out_note = &out->voice.notes[key];

        /* Note is still on and on same channel. */
        if (model_note->channel == out_note->channel) {
            active_notes[note_count++] = key;
        }
        else {
            /* Note has either switched channels or should be off, so disable it on the
            * currently sounding channel. */
            mg_midi_noteoff(mg, out_note->channel, key);
            out_note->channel = CHANNEL_OFF;
            notes_have_changed = 1;
        }
    }

    /* Update active_note list on output voice. */
    if (notes_have_changed) {
        out->voice.note_count = note_count;
        for (i = 0; i < note_count; i++)
            out->voice.active_notes[i] = active_notes[i];
    }
}
