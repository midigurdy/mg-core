#include "mg.h"
#include "output.h"
#include "state.h"

static int mg_output_sync(struct mg_output *output);
static void mg_output_add_tokens(struct mg_output *output);
static void mg_output_calculate_tokens_per_tick(struct mg_output *output);
static int mg_output_next_id(void);

static int mg_output_stream_sync(struct mg_output *output, struct mg_stream *stream);
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

    output->id = mg_output_next_id();

    return output;
}

void mg_output_delete(struct mg_output *output)
{
    int i;

    if (output == NULL) return;

    if (output->close) {
        output->close(output);
    }

    for(i = 0; i < output->stream_count; i++) {
        free(output->stream[i]);
    }

    free(output);
}

// FIXME: add a more rubust way to generate the output id!
int mg_output_next_id(void)
{
    static int output_id = 0;

    return output_id++;
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
            if (output->skip_iterations > 0) {
                output->skip_iterations--;
                continue;
            }

            mg_output_add_tokens(output);

            if (mg_output_sync(output)) {
                /* If there was an error during sync of this output, skip it for 1 second (1000 core
                 * worker iterations) */
                output->skip_iterations = 1000;
            }
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

static int mg_output_sync(struct mg_output *output)
{
    int i;
    struct mg_stream *stream;

    for (i = 0; i < output->stream_count; i++) {
        stream = output->stream[i];
        if (stream->enabled) {
            if (mg_output_stream_sync(output, stream)) {
                return -1;
            }
        }
    }

    return 0;
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

static int mg_output_stream_sync(struct mg_output *output, struct mg_stream *stream)
{
    int i;
    int key;
    int ret;

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
            ret = output->noteon(output, src_note->channel, key, src_note->velocity);
            if (ret < 0) {
                /* If sending a noteon failed and we want to abort, make sure
                 * we record which notes we have already sent noteons for
                 * before exiting. No need to consider notes which have changed
                 * channels (in which case it would already be in the
                 * dst->active_notes array), as the core will make sure that a
                 * channel reset is sent before switching the channel of a string. */
                if (notes_have_changed) {
                    for (i = 0; i < note_count; i++) {
                        dst->active_notes[dst->note_count++] = active_notes[i];
                    }
                }

                return -1;
            }
            stream->tokens -= ret;
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
            ret = output->noteoff(output, dst_note->channel, key);
            if (ret < 0) {
                /* If sending a noteoff failed and we want to abort, update the
                 * dst->active_notes array immediately, but make sure to also
                 * add all notes for which we haven't checked for a noteoff yet. */

                if (notes_have_changed) {
                    /* Add all notes which we haven't checked yet (and therefore exclude notes for
                       which we have sent noteoffs already. */
                    for (; i < dst->note_count; i++) {
                        active_notes[note_count++] = dst->active_notes[i];
                    }

                    /* Update active_note list on destination. */
                    dst->note_count = note_count;
                    for (i = 0; i < note_count; i++) {
                        dst->active_notes[i] = active_notes[i];
                    }
                }

                return -1;
            }
            stream->tokens -= ret;
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
        ret = sender(output, stream);
        if (ret < 0) {
            /* No need to clean up anything here, as senders are supposed to only update the
             * destination state if they succeeded in sending their message. */
            return -1;
        }
        stream->tokens -= ret;
        stream->sender_idx++;
        stream->sender_idx %= stream->sender_count;
    }

    return 0;
}
