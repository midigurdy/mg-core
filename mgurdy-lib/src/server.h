#ifndef _MG_SERVER_H_
#define _MG_SERVER_H_

#include "mg.h"

void *mg_server_thread(void *args);

void mg_server_report_wheel();
void mg_server_record_wheel_data(int position, int speed, int chien_volume, int chien_speed);

void mg_server_report_keys(const struct mg_key *keys);
int mg_server_key_client_count();

#endif
