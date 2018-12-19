#include "fluidsynth.h"

#include "output.h"

static int add_melody_stream(struct mg_output *output, struct mg_string *string);
static int add_trompette_stream(struct mg_output *output, struct mg_string *string);
static int add_drone_stream(struct mg_output *output, struct mg_string *string);
static int add_keynoise_stream(struct mg_output *output, struct mg_string *string);

static int mg_output_fluid_noteon(struct mg_output *output, int channel, int note, int velocity);
static int mg_output_fluid_noteoff(struct mg_output *output, int channel, int note);
static int mg_output_fluid_reset(struct mg_output *output, int channel);

static int mg_output_fluid_expression(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_volume(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_pitch(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_channel_pressure(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_balance(struct mg_output *output, struct mg_stream *stream);


struct mg_output *new_fluid_output(struct mg_core *mg)
{
    struct mg_output *output;
    
    output = mg_output_new();
    if (output == NULL) {
        return NULL;
    }

    output->data = mg->fluid;
    output->noteon = mg_output_fluid_noteon;
    output->noteoff = mg_output_fluid_noteoff;
    output->reset = mg_output_fluid_reset;
    output->tokens_per_tick = 0; /* no rate limiting for internal synth */

    if (!(add_melody_stream(output, &mg->state.melody[0]) &&
          add_melody_stream(output, &mg->state.melody[1]) &&
          add_melody_stream(output, &mg->state.melody[3]) &&
          add_trompette_stream(output, &mg->state.trompette[0]) &&
          add_trompette_stream(output, &mg->state.trompette[1]) &&
          add_trompette_stream(output, &mg->state.trompette[2]) &&
          add_drone_stream(output, &mg->state.drone[0]) &&
          add_drone_stream(output, &mg->state.drone[1]) &&
          add_drone_stream(output, &mg->state.drone[2]) &&
          add_keynoise_stream(output, &mg->state.keynoise)))
    {
        mg_output_delete(output);
        return NULL;
    }

    return output;
}


static int add_melody_stream(struct mg_output *output, struct mg_string *string)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_expression;
    stream->sender[stream->sender_count++] = mg_output_fluid_pitch;
    stream->sender[stream->sender_count++] = mg_output_fluid_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;

    output->stream[output->stream_count++] = stream;

    stream->enabled = 1;

    return 1;
}

static int add_trompette_stream(struct mg_output *output, struct mg_string *string)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_expression;
    stream->sender[stream->sender_count++] = mg_output_fluid_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;

    output->stream[output->stream_count++] = stream;

    stream->enabled = 1;

    return 1;
}

static int add_drone_stream(struct mg_output *output, struct mg_string *string)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_expression;
    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;

    output->stream[output->stream_count++] = stream;

    stream->enabled = 1;

    return 1;
}

static int add_keynoise_stream(struct mg_output *output, struct mg_string *string)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;

    output->stream[output->stream_count++] = stream;

    stream->enabled = 1;

    return 1;
}

static int mg_output_fluid_noteon(struct mg_output *output, int channel, int note, int velocity)
{
    fluid_synth_noteon((fluid_synth_t *)output->data, channel, note, velocity);
    return 0;
}

static int mg_output_fluid_noteoff(struct mg_output *output, int channel, int note)
{
    /* Don't send note off events for the keynoise channel. Samples on that channel are never supposed
     * to loop anyway */
    if (channel != MG_KEYNOISE) {
        fluid_synth_noteoff((fluid_synth_t *)output->data, channel, note);
    }
    return 0;
}

static int mg_output_fluid_reset(struct mg_output *output, int channel)
{
    fluid_synth_cc((fluid_synth_t *)output->data, channel, MG_CC_ALL_SOUNDS_OFF, 0);
    fluid_synth_cc((fluid_synth_t *)output->data, channel, MG_CC_ALL_CTRL_OFF, 0);
    return 0;
}

static int mg_output_fluid_expression(struct mg_output *output, struct mg_stream *stream)
{
    int expression = stream->string->model.expression;

    if (stream->dst.expression != expression) {
        fluid_synth_cc((fluid_synth_t *)output->data, stream->string->channel, MG_CC_EXPRESSION, expression);
        stream->dst.expression = expression;
        return 3000;
    }

    return 0;
}

static int mg_output_fluid_volume(struct mg_output *output, struct mg_stream *stream)
{
    int volume = stream->string->model.volume;

    if (stream->dst.volume != volume) {
        fluid_synth_cc((fluid_synth_t *)output->data, stream->string->channel, MG_CC_VOLUME, volume);
        stream->dst.volume = volume;
    }

    return 0;
}

static int mg_output_fluid_pitch(struct mg_output *output, struct mg_stream *stream)
{
    int pitch = stream->string->model.pitch;

    if (stream->dst.pitch != pitch) {
        fluid_synth_pitch_bend((fluid_synth_t *)output->data, stream->string->channel, pitch);
        stream->dst.pitch = pitch;
    }

    return 0;
}

static int mg_output_fluid_channel_pressure(struct mg_output *output, struct mg_stream *stream)
{
    int pressure = stream->string->model.pressure;

    if (stream->dst.pressure != pressure) {
        fluid_synth_channel_pressure((fluid_synth_t *)output->data, stream->string->channel, pressure);
        stream->dst.pressure = pressure;
    }

    return 0;
}

static int mg_output_fluid_balance(struct mg_output *output, struct mg_stream *stream)
{
    int panning = stream->string->model.panning;

    if (stream->dst.panning != panning) {
        fluid_synth_cc((fluid_synth_t *)output->data, stream->string->channel, MG_CC_PANNING, panning);
        stream->dst.panning = panning;
    }

    return 0;
}