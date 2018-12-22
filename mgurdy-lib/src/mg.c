#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <pthread.h>

#include "mg.h"
#include "server.h"
#include "state.h"
#include "worker.h"
#include "output.h"
#include "output_fluid.h"
#include "output_midi.h"


static struct mg_core mg_core;


/* Public API functions */

int mg_start(fluid_synth_t *fluid)
{
    int err = 0;

    if (mg_initialize()) {
        fprintf(stderr, "Error during initialization!\n");
        return -1;
    }

    err = pthread_mutex_lock(&mg_core.mutex);
    if (err) {
        perror("Unable to aquire mg_core mutex");
        return err;
    }

    if (mg_core.started) {
        fprintf(stderr, "MidiGurdy core already started!\n");
        err = -1;
        goto exit;
    }

    mg_core.fluid = fluid;
    mg_core.should_stop = 0;
    mg_core.halt_midi_output = 0;

    struct mg_output *output;
    output = new_fluid_output(&mg_core);
    if (output == NULL) {
        fprintf(stderr, "Unable to create FluidSynth output\n");
        err = -1;
        goto cleanup_core;
    }
    mg_core.outputs[MG_OUTPUT_FLUID] = output;
    mg_core.output_count++;
    mg_output_enable(output, 1);

    err = pthread_create(&mg_core.worker_pth, NULL, mg_worker_thread,
            &mg_core);
    if (err) {
        perror("Unable to start worker thread");
        goto cleanup_core;
    }

    err = pthread_create(&mg_core.server_pth, NULL, mg_server_thread,
            &mg_core);
    if (err) {
        perror("Unable to start server thread");
        goto cleanup_worker;
    }

    mg_core.started = 1;
    goto exit;


cleanup_worker:
    mg_core.should_stop = 1;
    err = pthread_join(mg_core.worker_pth, NULL);
    if (err)
        perror("Unable to join worker thread");

cleanup_core:
    mg_core.fluid = NULL;


exit:
    err = pthread_mutex_unlock(&mg_core.mutex);
    if (err) {
        perror("Unable to release mg_core mutex");
    }

    return err;
}


int mg_stop(void)
{
    int err = 0;

    err = pthread_mutex_lock(&mg_core.mutex);
    if (err) {
        perror("Unable to aquire mg_core mutex");
        return err;
    }

    if (!mg_core.started) {
        fprintf(stderr, "MidiGurdy not running!\n");
        err = -1;
        goto exit;
    }

    mg_core.should_stop = 1;

    err = pthread_join(mg_core.worker_pth, NULL);
    if (err) {
        perror("Unable to join worker thread");
        goto exit;
    }

    mg_core.fluid = NULL;
    mg_core.started = 0;

exit:
    err = pthread_mutex_unlock(&mg_core.mutex);
    if (err) {
        perror("Unable to release mg_core mutex");
    }

    return err;
}


int mg_initialize()
{
    pthread_mutexattr_t attr;

    if (mg_core.initialized) {
        return 0;
    }

    pthread_mutexattr_init(&attr);
    pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    pthread_mutex_init(&mg_core.mutex, &attr);

    if (pthread_mutex_init(&mg_core.state.mutex, &attr));

    pthread_mutexattr_destroy(&attr);

    mg_state_init(&mg_core.state);

    mg_core.initialized = 1;

    return 0;
}

int mg_set_key_on_debounce(int num)
{
    int err = 0;
    struct mg_state *s = &mg_core.state;

    err = mg_state_lock(s);
    if (err)
        return err;

    s->key_on_debounce = num;

    return mg_state_unlock(s);
}

int mg_set_key_off_debounce(int num)
{
    int err = 0;
    struct mg_state *s = &mg_core.state;

    err = mg_state_lock(s);
    if (err)
        return err;

    s->key_off_debounce = num;

    return mg_state_unlock(s);
}

int mg_set_base_note_delay(int num)
{
    int err = 0;
    struct mg_state *s = &mg_core.state;

    err = mg_state_lock(s);
    if (err)
        return err;

    s->base_note_delay = num;

    return mg_state_unlock(s);
}

int mg_set_pitchbend_factor(float factor)
{
    int err = 0;
    struct mg_state *s = &mg_core.state;

    err = mg_state_lock(s);
    if (err)
        return err;

    s->pitchbend_factor = factor;

    return mg_state_unlock(s);
}


int mg_set_string(struct mg_string_config *configs)
{
    int err = 0;
    int snum;
    struct mg_state *s = &mg_core.state;
    struct mg_string *st;
    struct mg_string_config *c;

    err = mg_state_lock(s);
    if (err)
        return err;

    for(c = configs; ; c++) {
        if (c->param == MG_PARAM_END)
            break;

        snum = c->string;

        if (snum >= MG_MELODY1 && snum <= MG_MELODY3)
            st = &s->melody[snum];
        else if (snum >= MG_TROMPETTE1 && snum <= MG_TROMPETTE3)
            st = &s->trompette[snum - MG_TROMPETTE1];
        else if (snum >= MG_DRONE1 && snum <= MG_DRONE3)
            st = &s->drone[snum - MG_DRONE1];
        else if (snum == MG_KEYNOISE) {
            st = &s->keynoise;
        }
        else {
            fprintf(stderr, "Invalid string specified: %d\n", c->string);
            err = -1;
            goto exit;
        }

        switch(c->param) {
            case MG_PARAM_MUTE:
                mg_string_set_mute(st, c->val);
                break;
            case MG_PARAM_VOLUME:
                mg_string_set_volume(st, c->val);
                break;
            case MG_PARAM_CHANNEL:
                // printf("string %d channel: %d\n", snum, c->val);
                // printf("channel %d\n", c->val);
                break;
            case MG_PARAM_BASE_NOTE:
                mg_string_set_base_note(st, c->val);
                break;
            case MG_PARAM_PANNING:
                st->panning = c->val;
                break;
            case MG_PARAM_POLYPHONIC:
                st->polyphonic = c->val ? 1 : 0;
                break;
            case MG_PARAM_EMPTY_KEY:
                if (c->val < 0)
                    st->empty_key = 0;
                else if (c->val > 23)
                    st->empty_key = 23;
                else
                    st->empty_key = c->val;
                break;
            case MG_PARAM_THRESHOLD:
                mg_string_set_chien_threshold(st, c->val);
                break;
            case MG_PARAM_ATTACK:
                // printf("string %d attack key: %d\n", snum, c->val);
                break;
            case MG_PARAM_NOTE_ENABLE:
                mg_string_set_fixed_note(st, c->val, 127);
                break;
            case MG_PARAM_NOTE_DISABLE:
                mg_string_set_fixed_note(st, c->val, 0);
                break;
            case MG_PARAM_NOTE_CLEAR:
                mg_string_clear_fixed_notes(st);
                break;
            case MG_PARAM_RESET:
                mg_output_all_reset_string(&mg_core, st);
                break;
            case MG_PARAM_MODE:
                if (c->val >= 0 && c->val <= 2) {
                    st->mode = c->val;
                }
                break;
            default:
                fprintf(stderr, "Invalid param specified: %d\n",
                        c->param);
                err = -1;
                goto exit;
        }
    }

exit:
    return mg_state_unlock(s);
}

int mg_add_midi_output(const char *device)
{
    int ret;
    struct mg_output *output;

    output = new_midi_output(&mg_core, device);
    if (output == NULL) {
        return -1;
    }

    mg_output_enable(output, 1);

    ret = mg_state_lock(&mg_core.state);
    if (ret) {
        fprintf(stderr, "Unable to get state lock!\n");
        mg_output_delete(output);
        return ret;
    }

    if (mg_core.output_count >= MG_OUTPUT_COUNT) {
        fprintf(stderr, "Maximum output count reached\n");
        mg_output_delete(output);
        ret = -1;
        goto exit;
    }

    mg_core.outputs[mg_core.output_count++] = output;

    ret = output->id;

exit:
    mg_state_unlock(&mg_core.state);
    return ret;
}


int mg_remove_midi_output(int output_id)
{
    int err;
    int output_idx;
    struct mg_output *output = NULL;

    err = mg_state_lock(&mg_core.state);
    if (err) {
        fprintf(stderr, "Unable to get state lock!\n");
        return err;
    }

    // find the output by id
    for (output_idx = 0; output_idx < mg_core.output_count; output_idx++) {
        output = mg_core.outputs[output_idx];
        if (output->id == output_id)
            break;
    }

    // remove output from output list
    if (output_idx < mg_core.output_count) {
        // fill the gap by moving following outputs up one slot
        for (output_idx++; output_idx < mg_core.output_count; output_idx++) {
            mg_core.outputs[output_idx - 1] = mg_core.outputs[output_idx];
        }
        mg_core.output_count--;
    }

    /* no need to hold the state lock while deleting the already removed output */
    mg_state_unlock(&mg_core.state);

    mg_output_delete(output);

    return 0;
}


int mg_get_wheel_gain(void)
{
    return mg_core.wheel.gain;
}


int mg_halt_midi_output(int halted)
{
    int err;

    err = mg_state_lock(&mg_core.state);
    if (err) {
        fprintf(stderr, "Unable to get state lock!\n");
        return err;
    }

    mg_core.halt_midi_output = halted;

    if (halted) {
        mg_output_all_reset(&mg_core);
    }

    return mg_state_unlock(&mg_core.state);
}


int mg_get_mapping(struct mg_map *dst, int idx)
{
    struct mg_map *src = mg_state_get_mapping(&mg_core.state, idx);
    if (src == NULL)
        return -1;

    dst->count = src->count;
    memcpy(dst->ranges, src->ranges, sizeof(src->ranges));

    return 0;
}


int mg_set_mapping(const struct mg_map *src, int idx)
{
    struct mg_map *dst = mg_state_get_mapping(&mg_core.state, idx);
    if (dst == NULL)
        return -1;

    if (mg_state_lock(&mg_core.state))
        return -1;

    if (src->count >= 1) {
        dst->count = src->count;
        memcpy(dst->ranges, src->ranges, sizeof(src->ranges));
    } else {
        fprintf(stderr, "failed to set mapping with 0 range (%d)\n", src->count);
    }

    return mg_state_unlock(&mg_core.state);
}


int mg_reset_mapping_ranges(int idx)
{
    struct mg_map *src;

    src = mg_state_get_default_mapping(idx);
    if (src == NULL)
        return -1;

    return mg_set_mapping(src, idx);
}

int mg_calibrate_set_key(int key, float pressure_adjust, float velocity_adjust)
{
    if (key < 0 || key > KEY_COUNT - 1) {
        return -1;
    }

    mg_core.key_calib[key].pressure_adjust = pressure_adjust;
    mg_core.key_calib[key].velocity_adjust = velocity_adjust;

    return 0;
}

int mg_calibrate_get_key(int key, float *pressure_adjust, float *velocity_adjust)
{
    if (key < 0 || key > KEY_COUNT - 1) {
        return -1;
    }

    *pressure_adjust = mg_core.key_calib[key].pressure_adjust;
    *velocity_adjust = mg_core.key_calib[key].velocity_adjust;

    return 0;
}

/* End public API */
