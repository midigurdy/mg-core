#include "fluidsynth.h"

#include "output.h"

static int add_melody_stream(struct mg_output *output, struct mg_string *string, int channel);
static int add_trompette_stream(struct mg_output *output, struct mg_string *string, int channel);
static int add_drone_stream(struct mg_output *output, struct mg_string *string, int channel);
static int add_keynoise_stream(struct mg_output *output, struct mg_string *string, int channel);

static int mg_output_fluid_noteon(struct mg_output *output, int channel, int note, int velocity);
static int mg_output_fluid_noteoff(struct mg_output *output, int channel, int note);
static int mg_output_fluid_reset(struct mg_output *output, int channel);

static int mg_output_fluid_expression(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_volume(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_pitch(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_channel_pressure(struct mg_output *output, struct mg_stream *stream);
static int mg_output_fluid_balance(struct mg_output *output, struct mg_stream *stream);


struct mg_output *new_fluid_output(struct mg_core *mg, fluid_synth_t *fluid)
{
    struct mg_output *output;
    
    output = mg_output_new();
    if (output == NULL) {
        return NULL;
    }

    output->data = fluid;
    output->noteon = mg_output_fluid_noteon;
    output->noteoff = mg_output_fluid_noteoff;
    output->reset = mg_output_fluid_reset;
    output->tokens_per_tick = 0; /* no rate limiting for internal synth */

    if (!(add_melody_stream(output, &mg->state.melody[0], 0) &&
          add_melody_stream(output, &mg->state.melody[1], 1) &&
          add_melody_stream(output, &mg->state.melody[2], 2) &&
          add_trompette_stream(output, &mg->state.trompette[0], 6) &&
          add_trompette_stream(output, &mg->state.trompette[1], 7) &&
          add_trompette_stream(output, &mg->state.trompette[2], 8) &&
          add_drone_stream(output, &mg->state.drone[0], 3) &&
          add_drone_stream(output, &mg->state.drone[1], 4) &&
          add_drone_stream(output, &mg->state.drone[2], 5) &&
          add_keynoise_stream(output, &mg->state.keynoise, 9)))
    {
        mg_output_delete(output);
        return NULL;
    }

    return output;
}


static int add_melody_stream(struct mg_output *output, struct mg_string *string, int channel)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0, channel);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_expression;
    stream->sender[stream->sender_count++] = mg_output_fluid_pitch;
    stream->sender[stream->sender_count++] = mg_output_fluid_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;

    output->stream[output->stream_count++] = stream;

    return 1;
}

static int add_trompette_stream(struct mg_output *output, struct mg_string *string, int channel)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0, channel);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_expression;
    stream->sender[stream->sender_count++] = mg_output_fluid_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;

    output->stream[output->stream_count++] = stream;

    return 1;
}

static int add_drone_stream(struct mg_output *output, struct mg_string *string, int channel)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0, channel);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_expression;
    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;

    output->stream[output->stream_count++] = stream;

    return 1;
}

static int add_keynoise_stream(struct mg_output *output, struct mg_string *string, int channel)
{
    struct mg_stream *stream = mg_output_stream_new(string, 0, channel);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_fluid_volume;
    stream->sender[stream->sender_count++] = mg_output_fluid_balance;
    stream->sender[stream->sender_count++] = mg_output_fluid_channel_pressure;

    output->stream[output->stream_count++] = stream;

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
        fluid_synth_cc((fluid_synth_t *)output->data, stream->channel, MG_CC_EXPRESSION, expression);
        stream->dst.expression = expression;
    }

    return 0;
}

static int mg_output_fluid_volume(struct mg_output *output, struct mg_stream *stream)
{
    // volume taken directly from string, no modelling involved
    int volume = stream->string->volume;

    if (stream->dst.volume != volume) {
        fluid_synth_cc((fluid_synth_t *)output->data, stream->channel, MG_CC_VOLUME, volume);
        stream->dst.volume = volume;
    }

    return 0;
}

static int mg_output_fluid_pitch(struct mg_output *output, struct mg_stream *stream)
{
    int pitch = stream->string->model.pitch;

    if (stream->dst.pitch != pitch) {
        fluid_synth_pitch_bend((fluid_synth_t *)output->data, stream->channel, pitch);
        stream->dst.pitch = pitch;
    }

    return 0;
}

static int mg_output_fluid_channel_pressure(struct mg_output *output, struct mg_stream *stream)
{
    int pressure = stream->string->model.pressure;

    if (stream->dst.pressure != pressure) {
        fluid_synth_channel_pressure((fluid_synth_t *)output->data, stream->channel, pressure);
        stream->dst.pressure = pressure;
    }

    return 0;
}

static int mg_output_fluid_balance(struct mg_output *output, struct mg_stream *stream)
{
    // panning is taken directly from the string, no modelling involved
    int panning = stream->string->panning;

    if (stream->dst.panning != panning) {
        fluid_synth_cc((fluid_synth_t *)output->data, stream->channel, MG_CC_PANNING, panning);
        stream->dst.panning = panning;
    }

    return 0;
}
