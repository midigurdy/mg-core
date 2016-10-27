#include "midi_lowlevel.h"

void mg_midi_noteon(struct mg_core *mg, int channel, int note, int velocity)
{
    fluid_synth_noteon(mg->fluid, channel, note, velocity);
}

void mg_midi_noteoff(struct mg_core *mg, int channel, int note)
{
    fluid_synth_noteoff(mg->fluid, channel, note);
}

void mg_midi_all_notes_off(struct mg_core *mg, int channel)
{
    fluid_synth_all_notes_off(mg->fluid, channel);
}

void mg_midi_cc(struct mg_core *mg, int channel, int control, int value)
{
    fluid_synth_cc(mg->fluid, channel, control, value);
}

void mg_midi_pitch_bend(struct mg_core *mg, int channel, int pitch)
{
    fluid_synth_pitch_bend(mg->fluid, channel, pitch);
}

void mg_midi_channel_pressure(struct mg_core *mg, int channel, int pressure)
{
    fluid_synth_channel_pressure(mg->fluid, channel, pressure);
}

void mg_midi_key_pressure(struct mg_core *mg, int channel, int note, int pressure)
{
    fluid_synth_key_pressure(mg->fluid, channel, note, pressure);
}
