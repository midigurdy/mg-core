#include <sched.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/types.h>

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
static void position_to_websockets(void);


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
        clock_gettime(CLOCK_MONOTONIC, &t);
        mg_timespec_add_us(&t, WORKER_INTERVAL_US);

        if (mg->started) {
            if (mg_worker_run(mg)) {
                fprintf(stderr, "Fatal error, terminating worker\n");
                goto cleanup;
            }
        }
    }

cleanup:
    mg_worker_cleanup(mg);

    return NULL;
}

static int mg_worker_run(struct mg_core *mg)
{
    int ret;
    int err;

    struct mg_state *state = &mg->state;
    struct mg_wheel *wheel = &mg->wheel;
    struct mg_keyboard *keyboard = &mg->keyboard;

    /* grab the core lock while we are working */
    err = mg_core_lock();
    if (err) {
        return err;
    }

    /* read any pending sensor values */
    ret = mg_sensors_read(mg);
    if (ret < 0) {
        fprintf(stderr, "Error while reading sensors\n");
        goto exit;
    }

    /* grab the state lock to update the output models */
    err = mg_state_lock(state);
    if (err) {
        goto exit;
    }

    mg_synth_update_sensors(wheel, keyboard, state);

    mg_output_all_update(mg);

    /* release state lock, nothing below will touch the state again */
    err = mg_state_unlock(state);
    if (err) {
        goto exit;
    }

    /* synchronize internal state with outputs */
    if (!mg->halt_outputs) {
        mg_output_all_sync(mg);
    }

    mg_server_record_wheel_data(wheel->position, wheel->speed);

    /* report to attached clients */
    position_to_websockets();
    if (mg_server_key_client_count()) {
        mg_server_report_keys(keyboard->keys);
    }

    err = 0;

exit:
    mg_core_unlock();
    return err;
}


/* Report the current position to any connected websocket listeners, but only
 * every MG_WHEEL_REPORT_INTERVAL call */
static void position_to_websockets(void)
{
    static int calls = 0;

    if (calls < MG_WHEEL_REPORT_INTERVAL) {
        calls++;
        return;
    }

    mg_server_report_wheel();
    calls = 0;
}

static void stack_prefault(void)
{
    unsigned char dummy[MAX_SAFE_STACK];
    memset(dummy, 0, MAX_SAFE_STACK);
}
