#include <sched.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/types.h>

#include <fluidsynth.h>

#include "sensors.h"
#include "server.h"
#include "synth.h"
#include "utils.h"
#include "state.h"
#include "output.h"

#include "worker.h"


#define MAX_SAFE_STACK (8*1024)

static int mg_worker_run(struct mg_core *mg);
static void stack_prefault(void);
static void position_to_websockets(struct mg_core *mg);


int mg_worker_init(struct mg_core *mg)
{
    int err;

    err = mg_sensors_init(mg);
    if (err)
        return err;

    return err;
}


void mg_worker_cleanup(struct mg_core *mg)
{
    mg_sensors_cleanup(mg);
}


void *mg_worker_thread(void *args)
{
    struct sched_param param;
    struct timespec t;
    struct mg_core *mg = args;

    prctl(PR_SET_NAME, "mgcore-worker\0", NULL, NULL, NULL);

    param.sched_priority = WORKER_PRIO;
    if (sched_setscheduler(0, SCHED_FIFO, &param) == -1) {
        perror("Warning: Failed to set worker thread priority");
    }

    /* Lock memory and prefault the whole stack so that we don't get
     * pagefaults while while running the main loop */
    if (mlockall(MCL_CURRENT|MCL_FUTURE) == -1) {
        perror("Warning: Failed to lock memory");
    }
    stack_prefault();

    if (mg_worker_init(mg)) {
        fprintf(stderr,"Error initializing worker!\n");
        mg->worker_retval = -1;
        return NULL;
    }

    clock_gettime(CLOCK_MONOTONIC, &t);
    mg_timespec_add_us(&t, WORKER_INTERVAL_US);

    while(!mg->should_stop) {
        if (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &t, NULL)) {
            perror("Error while sleeping in worker thread");
            goto cleanup;
        }

        if (mg->started) {
            if (mg_worker_run(mg)) {
                fprintf(stderr, "Fatal error, terminating worker\n");
                goto cleanup;
            }
        }

        /* TODO: maybe use the previously fetched time in t to have a more
         * constant interval? */
        clock_gettime(CLOCK_MONOTONIC, &t);
        mg_timespec_add_us(&t, WORKER_INTERVAL_US);
    }

cleanup:
    mg_worker_cleanup(mg);

    return NULL;
}

static int mg_worker_run(struct mg_core *mg)
{
    int ret;
    int err;
    static int count = 0;

    /* read any pending sensor values */
    ret = mg_sensors_read(mg);
    if (ret < 0) {
        fprintf(stderr, "Error while reading sensors\n");
        return -1;
    }

    /* update the internal model state */
    err = mg_state_lock(&mg->state);
    if (err) {
        fprintf(stderr, "Unable to get state lock!\n");
        return err;
    }

    mg_synth_update(mg);

    /* synchronize internal state with outputs */
    if (!mg->halt_midi_output) {
        mg_output_all_sync(mg);
    }

    err = mg_state_unlock(&mg->state);
    if (err) {
        fprintf(stderr, "Unable to unlock state!\n");
    }

    /* report to attached clients */
    position_to_websockets(mg);
    if (mg_server_key_client_count()) {
        mg_server_report_keys(mg->keys);
    }

    if (count < 1000) {
        count ++;
    } else {
        count = 0;
        // mg_midi_stats();
    }

    return 0;
}


/* Report the current position to any connected websocket listeners, but only
 * every MG_WHEEL_REPORT_INTERVAL call */
static void position_to_websockets(struct mg_core *mg)
{
    static int calls = 0;
    static int prev_pos = 0;
    static int prev_speed = 0;
    static int prev_chien_volume = 0;
    static int prev_chien_speed = 0;
    int pos;
    int speed;
    int chien_volume;
    int chien_speed;

    pos = mg->wheel.position;
    speed = mg->wheel.speed;
    chien_volume = mg->chien_volume;
    chien_speed = mg->chien_speed;
    if (pos != prev_pos || speed != prev_speed || chien_volume != prev_chien_volume || chien_speed != prev_chien_speed) {
        mg_server_record_wheel_data(pos, speed, chien_volume, chien_speed);
        prev_pos = pos;
        prev_speed = speed;
        prev_chien_volume = chien_volume;
        prev_chien_speed = chien_speed;
    }

    if (calls >= MG_WHEEL_REPORT_INTERVAL) {
        mg_server_report_wheel();
        calls = 0;
    }
    else if (calls < MG_WHEEL_REPORT_INTERVAL)
        calls++;
}

static void stack_prefault(void)
{
    unsigned char dummy[MAX_SAFE_STACK];
    memset(dummy, 0, MAX_SAFE_STACK);
}
