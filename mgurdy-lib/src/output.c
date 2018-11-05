#include "mg.h"
#include "output.h"
#include "state.h"

static void mg_output_sync(struct mg_output *output);
static void mg_output_add_tokens(struct mg_output *output);
static void mg_output_calculate_tokens_per_tick(struct mg_output *output);

static void mg_output_stream_sync(struct mg_output *output, struct mg_stream *stream);
static void mg_output_stream_reset(struct mg_output *output, struct mg_stream *stream);


/* Public functions */

struct mg_output *mg_output_new(void)
{
    struct mg_output *output;

    output = malloc(sizeof(struct mg_output));
    if (output == NULL) {
        printf("Out of memory!\n");
        return NULL;
    }

    memset(output, 0, sizeof(struct mg_output));

    return output;
}

void mg_output_delete(struct mg_output *output)
{
    int i;

    if (output == NULL) return;

    for(i = 0; i < output->stream_count; i++) {
        free(output->stream[i]);
    }

    free(output);
}

struct mg_stream *mg_output_stream_new(struct mg_string *string, int tokens_percent)
{
    struct mg_stream *stream;

    stream = malloc(sizeof(struct mg_stream));
    if (stream == NULL) {
        printf("Out of memory!\n");
        return NULL;
    }
    memset(stream, 0, sizeof(struct mg_stream));

    stream->string = string;
    stream->tokens_percent = tokens_percent;

    return stream;
}

void mg_output_all_sync(struct mg_core *mg)
{
    int i;
    struct mg_output *output;

    for (i = 0; i < mg->output_count; i++) {
        output = mg->outputs[i];
        if (output->enabled) {
            mg_output_add_tokens(output);
            mg_output_sync(output);
        }
    }
}

void mg_output_all_reset(struct mg_core *mg)
{
    int i;
    struct mg_output *output;

    for (i = 0; i < mg->output_count; i++) {
        output = mg->outputs[i];
        if (output->enabled) {
            mg_output_reset(output);
        }
    }
}

void mg_output_all_reset_string(struct mg_core *mg, struct mg_string *string)
{
    int i, k;
    struct mg_output *output;

    for (k = 0; k < mg->output_count; k++) {
        output = mg->outputs[k];

        for (i = 0; i < output->stream_count; i++) {
            if (output->stream[i]->string == string) {
                mg_output_stream_reset(output, output->stream[i]);
                break;
            }
        }
    }
}

void mg_output_enable(struct mg_output *output, int enable)
{
    if (output->enabled == enable) {
        return;
    }

    output->enabled = enable;

    mg_output_calculate_tokens_per_tick(output);
}

void mg_output_reset(struct mg_output *output)
{
    for (int i = 0; i < output->stream_count; i++) {
        mg_output_stream_reset(output, output->stream[i]);
    }
}


/* Private functions */

static void mg_output_sync(struct mg_output *output)
{
    int i;
    struct mg_stream *stream;

    for (i = 0; i < output->stream_count; i++) {
        stream = output->stream[i];
        if (stream->enabled) {
            mg_output_stream_sync(output, stream);
        }
    }
}

static void mg_output_add_tokens(struct mg_output *output)
{
    int i;
    struct mg_stream *stream;

    if (output->tokens_per_tick) {
        for (i = 0; i < output->stream_count; i++) {
            stream = output->stream[i];
            if (stream->enabled && stream->tokens < stream->max_tokens) {
                stream->tokens = MIN(stream->tokens + stream->tokens_per_tick, stream->max_tokens);
            }
        }
    } else {
        for (i = 0; i < output->stream_count; i++) {
            output->stream[i]->tokens = 0;
        }
    }
}

static void mg_output_calculate_tokens_per_tick(struct mg_output *output)
{
    int i;
    int toks = output->tokens_per_tick;
    struct mg_stream *stream;

    /* Add unused tokens from the disabled streams to the total available tokens, so that
       it gets distributed to all enabled channels according to their token ratio */
    for (i = 0; i < output->stream_count; i++) {
        stream = output->stream[i];
        if (!stream->enabled) {
            toks += (stream->tokens_percent * output->tokens_per_tick) / 100;
            stream->tokens_per_tick = 0;
        }
    }

    /* distribute the available tokens across all enabled channels */
    for (i = 0; i < output->stream_count; i++) {
        stream = output->stream[i];
        if (stream->enabled) {
            stream->tokens_per_tick = stream->tokens_percent * toks / 100;
        }
    }

    /* debug */
    int sum = 0;
    for (i = 0; i < output->stream_count; i++) {
        sum += output->stream[i]->tokens_per_tick;
    }
    if (sum != output->tokens_per_tick) {
        printf("Output tokens not distributed optimally: output tokens = %d, stream token sum = %d\n",
                output->tokens_per_tick, sum);
    }
}

static void mg_output_stream_reset(struct mg_output *output, struct mg_stream *stream)
{
    output->reset(output, stream->string->channel);
    mg_state_reset_output_voice(&stream->dst);
}

static void mg_output_stream_sync(struct mg_output *output, struct mg_stream *stream)
{
    int i;
    int key;

    int active_notes[NUM_NOTES];
    int note_count = 0;
    int notes_have_changed = 0;

    struct mg_note *src_note;
    struct mg_note *dst_note;
    struct mg_voice *src = &stream->string->model;
    struct mg_voice *dst = &stream->dst;

    /* Send note on events - these are never rate limited */
    for (i = 0; i < src->note_count; i++) {
        key = src->active_notes[i];
        src_note = &src->notes[key];
        dst_note = &dst->notes[key];

        if (src_note->channel != dst_note->channel) {
            stream->tokens -= output->noteon(output, src_note->channel, key, src_note->velocity);
            dst_note->channel = src_note->channel;
            active_notes[note_count++] = key;
            notes_have_changed = 1;
        }
    }

    /* Send note off events - also never rate limited */
    for (i = 0; i < dst->note_count; i++) {
        key = dst->active_notes[i];
        dst_note = &dst->notes[key];
        src_note = &src->notes[key];

        if (dst_note->channel == src_note->channel) {
            active_notes[note_count++] = key;
        }
        else {
            stream->tokens -= output->noteoff(output, dst_note->channel, key);
            dst_note->channel = CHANNEL_OFF;
            notes_have_changed = 1;
        }
    }

    /* Update active_note list on destination */
    if (notes_have_changed) {
        dst->note_count = note_count;
        for (i = 0; i < note_count; i++) {
            dst->active_notes[i] = active_notes[i];
        }
    }
        
    /* Send all other messages this output supports, with rate limit
     * and in a round-robin fashion */
    for (i = 0; i < stream->sender_count; i++) {
        if (output->tokens_per_tick > 0 && stream->tokens <= 0) {
            break;
        }
        mg_output_send_t *sender = stream->sender[stream->sender_idx];
        stream->tokens -= sender(output, stream);
        stream->sender_idx++;
        stream->sender_idx %= stream->sender_count;
    }
}
