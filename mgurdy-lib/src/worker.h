#ifndef _MG_WORKER_H_
#define _MG_WORKER_H_

#include "mg.h"

void *mg_worker_thread(void *args);
int mg_worker_init(struct mg_core *mg);
void mg_worker_cleanup(struct mg_core *mg);

#endif
