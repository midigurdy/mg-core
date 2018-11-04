#ifndef _MG_MIDI_H_
#define _MG_MIDI_H_

#include "mg.h"


#define MG_CC_VOLUME (7)
#define MG_CC_PANNING (8)  // uses balance control
#define MG_CC_EXPRESSION (11)
#define MG_CC_ALL_SOUNDS_OFF (0x78)
#define MG_CC_ALL_CTRL_OFF (0x79)

#define MG_KEYNOISE_CHANNEL (9)


void mg_midi_sync(struct mg_core *mg);
void mg_midi_reset_all(struct mg_core *mg);
void mg_midi_reset_string(struct mg_core *mg, struct mg_string *st);


#endif
