#ifndef _MG_OUTPUT_H_
#define _MG_OUTPUT_H_

#include "mg.h"

struct mg_output *mg_output_new(void);
void mg_output_delete(struct mg_output *output);

struct mg_stream *mg_output_stream_new(struct mg_string *string, int tokens_percent);

void mg_output_all_sync(struct mg_core *mg);
void mg_output_all_reset(struct mg_core *mg);
void mg_output_all_reset_string(struct mg_core *mg, struct mg_string *string);

void mg_output_reset(struct mg_output *output);
void mg_output_enable(struct mg_output *output, int enable);

#endif
