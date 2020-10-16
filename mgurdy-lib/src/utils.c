#include <errno.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>

#include "mg.h"
#include "utils.h"


void mg_timespec_add_us(struct timespec *t, int usecs)
{
    t->tv_nsec += usecs * 1000;
    while (t->tv_nsec >= NSEC_PER_SEC) {
        t->tv_nsec -= NSEC_PER_SEC;
        t->tv_sec++;
    }
}


int mg_nsleep(unsigned int nsec)
{
    struct timespec req={0};
    req.tv_nsec = nsec;

    while((clock_nanosleep(CLOCK_MONOTONIC, 0, &req, &req) < 0) &&
            (errno == EINTR)) {
        continue;
    }
    return 1;
}


int mg_usleep(unsigned int usecs)
{
    struct timespec req, t0, t1;
    unsigned int duration;

    if (usecs > 1) {
        return mg_nsleep(usecs * 1000);
    }

    clock_gettime(CLOCK_MONOTONIC, &t0);

    while(1) {
        req.tv_sec = 0;
        req.tv_nsec = 400; // effective ca 1700 nsecs
        while((clock_nanosleep(CLOCK_MONOTONIC, 0, &req, &req) < 0) &&
                (errno == EINTR)) {
            continue;
        }
        clock_gettime(CLOCK_MONOTONIC, &t1);
        duration = duration_us(t0, t1);
        if (duration >= usecs) {
            return 1;
        }
    }
}


int duration_us(struct timespec start, struct timespec end)
{
    struct timespec tmp;

    if ((end.tv_nsec - start.tv_nsec) < 0) {
        tmp.tv_sec = end.tv_sec - start.tv_sec - 1;
        tmp.tv_nsec = 1000000000 + end.tv_nsec - start.tv_nsec;
    }
    else {
        tmp.tv_sec = end.tv_sec - start.tv_sec;
        tmp.tv_nsec = end.tv_nsec - start.tv_nsec;
    }

    return tmp.tv_sec * 1000000 + (tmp.tv_nsec / 1000);
}

int duration_ns(struct timespec start, struct timespec end)
{
    struct timespec tmp;

    if ((end.tv_nsec - start.tv_nsec) < 0) {
        tmp.tv_sec = end.tv_sec - start.tv_sec - 1;
        tmp.tv_nsec = 1000000000 + end.tv_nsec - start.tv_nsec;
    }
    else {
        tmp.tv_sec = end.tv_sec - start.tv_sec;
        tmp.tv_nsec = end.tv_nsec - start.tv_nsec;
    }

    return tmp.tv_sec * 1000000000 + tmp.tv_nsec;
}


// round up if mapping bigger ranges to smaller ranges, otherwise round down
#define MAP_IMPL(x, in_min, in_max, out_min, out_max) \
    ( ((in_max - in_min) > (out_max - out_min)) ? \
      (x - in_min) * (out_max - out_min + 1) / (in_max - in_min + 1) + out_min \
      : \
      (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min )


/**
 * Multilinear map of integer values
 */
int map_value(int x, const struct mg_map *mapping)
{
    int i;

    assert(mapping->count >= 1);

    if (x <= mapping->ranges[0][0])
        return mapping->ranges[0][1];

    for (i=1; i < mapping->count; i++) {
        if (x > mapping->ranges[i][0])
            continue;

        return MAP_IMPL(x,
                mapping->ranges[i-1][0], mapping->ranges[i][0],
                mapping->ranges[i-1][1], mapping->ranges[i][1]);
    }

    // x is larger than last max so just return that 
    return mapping->ranges[mapping->count-1][1];
}


int ary_indexof(int val, int ary[], int size)
{
    int i;

    for (i=0; i<size; i++) {
        if (ary[i] == val) {
            return i;
        }
    }

    return -1;
}


int ary_remove(int val, int src[], int dst[], int size)
{
    int i;
    int c = 0;

    for (i=0; i<size; i++) {
        if (src[i] == val) continue;
        dst[c++] = src[i];
    }

    return c;
}


void ary_print(int ary[], int size)
{
    int i;

    printf("[");
    for (i=0; i<size; i++) {
        if (i!=0) {
            printf(", %d", ary[i]);
        } else {
            printf("%d", ary[i]);
        }
    }
    printf("]\n");
}


int mg_smooth(int val, int prev, float factor)
{
    if (val == prev)
        return val;

    float add = (1 - factor) * (val - prev);

    return prev + add + (val > prev ? 1 : 0);
}
