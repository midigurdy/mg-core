#ifndef _MG_STATE_H_
#define _MG_STATE_H_

#include "mg.h"

int mg_state_lock(struct mg_state *state);
int mg_state_unlock(struct mg_state *state);
int mg_state_init(struct mg_state *state);
void mg_state_reset_model_voice(struct mg_voice *voice);
void mg_state_reset_output_voice(struct mg_voice *voice);

void mg_string_clear_notes(struct mg_string *st);
void mg_string_set_base_note(struct mg_string *st, int base_note);
void mg_string_set_volume(struct mg_string *st, int volume);
void mg_string_set_mute(struct mg_string *st, int muted);
void mg_string_set_chien_threshold(struct mg_string *st, int threshold);

struct mg_map *mg_state_get_mapping(struct mg_state *state, int idx);
struct mg_map *mg_state_get_default_mapping(int idx);

#endif
