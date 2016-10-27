#ifndef _MG_MIDI_LOWLEVEL_H_
#define _MG_MIDI_LOWLEVEL_H_

#include "fluidsynth.h"

#include "mg.h"

void mg_midi_noteon(struct mg_core *mg, int channel, int note, int velocity);
void mg_midi_noteoff(struct mg_core *mg, int channel, int note);
void mg_midi_all_notes_off(struct mg_core *mg, int channel);
void mg_midi_cc(struct mg_core *mg, int channel, int control, int value);
void mg_midi_pitch_bend(struct mg_core *mg, int channel, int pitch);
void mg_midi_channel_pressure(struct mg_core *mg, int channel, int pressure);
void mg_midi_key_pressure(struct mg_core *mg, int channel, int note, int pressure);

#endif
