#ifndef _MG_UTILS_H_
#define _MG_UTILS_H_

#include <time.h>


int mg_nsleep(unsigned int nsec);
int mg_usleep(unsigned int usecs);
void mg_timespec_add_us(struct timespec *t, int usecs);

int duration_us(struct timespec start, struct timespec end);
int duration_ns(struct timespec start, struct timespec end);

int map(int x, int in_min, int in_max, int out_min, int out_max);
int multimap(int x, const int ranges[][2], int num_ranges);

int ary_indexof(int val, int ary[], int size);
int ary_remove(int val, int src[], int dst[], int size);
void ary_print(int ary[], int size);

int mg_smooth(int val, int prev, float factor);

#endif
