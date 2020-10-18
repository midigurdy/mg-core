#ifndef _MG_SYNTH_H_
#define _MG_SYNTH_H_

#include "mg.h"


void mg_synth_update_sensors(struct mg_wheel *wheel, struct mg_keyboard *kb,
        const struct mg_state *state);

void mg_synth_update_strings(struct mg_state *state,
        const struct mg_wheel *wheel, const struct mg_keyboard *kb);

#endif
