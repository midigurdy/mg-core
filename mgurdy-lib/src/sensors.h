#ifndef _MG_SENSORS_H_
#define _MG_SENSORS_H_

#include "mg.h"

#define MG_KEYS_DEVICE "/dev/input/event3"
#define MG_WHEEL_DEVICE "/dev/input/event4"

int mg_sensors_init(struct mg_core *mg);
void mg_sensors_cleanup(struct mg_core *mg);

int mg_sensors_read(struct mg_core *mg);

#endif
