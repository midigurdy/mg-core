#include <unistd.h>
#include <stdint.h>
#include <errno.h>
#include "output.h"
#include <fcntl.h>
#include <sys/stat.h>

static int add_melody_stream(struct mg_output *output, struct mg_string *string, int tokens_percent);
static int add_trompette_stream(struct mg_output *output, struct mg_string *string, int tokens_percent);
static int add_drone_stream(struct mg_output *output, struct mg_string *string, int tokens_percent);

static void mg_output_midi_close(struct mg_output *output);

static int mg_output_midi_noteon(struct mg_output *output, int channel, int note, int velocity);
static int mg_output_midi_noteoff(struct mg_output *output, int channel, int note);
static int mg_output_midi_reset(struct mg_output *output, int channel);

static int mg_output_midi_expression(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_volume(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_pitch(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_channel_pressure(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_balance(struct mg_output *output, struct mg_stream *stream);

static int mg_midi_chmsg1(struct mg_output *output, int msg, int channel, int val);
static int mg_midi_chmsg2(struct mg_output *output, int msg, int channel, int val1, int val2);
static int mg_midi_write(struct mg_output *output, uint8_t *buffer, size_t size);


#define MIDI_LSB(val) (val & 0x7F)
#define MIDI_MSB(val) ((val & (0x7F << 7)) >> 7)

#define MIDI_MSG_NOTEON                (0x90)
#define MIDI_MSG_NOTEOFF               (0x80)
#define MIDI_MSG_CONTROL_CHANGE        (0xB0)
#define MIDI_MSG_CHANNEL_PRESSURE      (0xD0)
#define MIDI_MSG_POLY_PRESSURE         (0xA0)
#define MIDI_MSG_PITCH_BEND            (0xE0)


struct mg_midi_info {
    int fp;
    char *device;
};


struct mg_output *new_midi_output(struct mg_core *mg, const char *device)
{
    struct mg_output *output;
    struct mg_midi_info *info;
    int fp;

    fp = open(device, O_WRONLY | O_NONBLOCK);
    if (fp < 0) {
        fprintf(stderr, "Error opening MIDI device\n");
        return NULL;
    }
    
    output = mg_output_new();
    if (output == NULL) {
        close(fp);
        return NULL;
    }

    info = malloc(sizeof(struct mg_midi_info));
    if (info == NULL) {
        mg_output_delete(output);
        close(fp);
        return NULL;
    }

    info->fp = fp;
    info->device = strdup(device);
    if (info->device == NULL) {
        fprintf(stderr, "Out of memory\n");
        mg_output_delete(output);
        close(fp);
        return NULL;
    }

    output->data = info;
    output->close = mg_output_midi_close;
    output->noteon = mg_output_midi_noteon;
    output->noteoff = mg_output_midi_noteoff;
    output->reset = mg_output_midi_reset;
    output->tokens_per_tick = 3000;

    if (!(add_melody_stream(output, &mg->state.melody[0], 60) &&
          add_trompette_stream(output, &mg->state.trompette[0], 30) &&
          add_drone_stream(output, &mg->state.drone[0], 10)))
    {
        mg_output_delete(output);
        return NULL;
    }

    return output;
}


static void mg_output_midi_close(struct mg_output *output)
{
    struct mg_midi_info *info = output->data;

    if (info == NULL)
        return;

    printf("closing fp\n");
    close(info->fp);
    printf("done\n");
    free(info->device);
    free(info);

    output->data = NULL;
}


static int add_melody_stream(struct mg_output *output, struct mg_string *string, int tokens_percent)
{
    struct mg_stream *stream = mg_output_stream_new(string, tokens_percent);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_midi_expression;
    stream->sender[stream->sender_count++] = mg_output_midi_pitch;
    stream->sender[stream->sender_count++] = mg_output_midi_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_midi_volume;
    stream->sender[stream->sender_count++] = mg_output_midi_balance;

    output->stream[output->stream_count++] = stream;

    stream->enabled = 1;
    stream->max_tokens = 9000;

    return 1;
}

static int add_trompette_stream(struct mg_output *output, struct mg_string *string, int tokens_percent)
{
    struct mg_stream *stream = mg_output_stream_new(string, tokens_percent);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_midi_expression;
    stream->sender[stream->sender_count++] = mg_output_midi_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_midi_volume;
    stream->sender[stream->sender_count++] = mg_output_midi_balance;

    output->stream[output->stream_count++] = stream;

    stream->enabled = 1;
    stream->max_tokens = 9000;

    return 1;
}

static int add_drone_stream(struct mg_output *output, struct mg_string *string, int tokens_percent)
{
    struct mg_stream *stream = mg_output_stream_new(string, tokens_percent);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_midi_expression;
    stream->sender[stream->sender_count++] = mg_output_midi_volume;
    stream->sender[stream->sender_count++] = mg_output_midi_balance;

    output->stream[output->stream_count++] = stream;

    stream->enabled = 1;
    stream->max_tokens = 9000;

    return 1;
}

static int mg_output_midi_noteon(struct mg_output *output, int channel, int note, int velocity)
{
    mg_midi_chmsg2(output, MIDI_MSG_NOTEON, channel, note, velocity);
    return 3000;
}

static int mg_output_midi_noteoff(struct mg_output *output, int channel, int note)
{
    mg_midi_chmsg2(output, MIDI_MSG_NOTEOFF, channel, note, 0);
    return 3000;
}

static int mg_output_midi_reset(struct mg_output *output, int channel)
{
    mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, channel, MG_CC_ALL_SOUNDS_OFF, 0);
    mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, channel, MG_CC_ALL_CTRL_OFF, 0);
    return 6000;
}

static int mg_output_midi_expression(struct mg_output *output, struct mg_stream *stream)
{
    int expression = stream->string->model.expression;
    if (expression == 0) {
        expression = 1;
    }

    if (stream->dst.expression != expression) {
        mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->string->channel, MG_CC_EXPRESSION, expression);
        stream->dst.expression = expression;
        return 3000;
    }

    return 0;
}

static int mg_output_midi_volume(struct mg_output *output, struct mg_stream *stream)
{
    int volume = stream->string->model.volume;

    if (stream->dst.volume != volume) {
        mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->string->channel, MG_CC_VOLUME, volume);
        stream->dst.volume = volume;
        return 3000;
    }

    return 0;
}

static int mg_output_midi_pitch(struct mg_output *output, struct mg_stream *stream)
{
    int pitch = stream->string->model.pitch;

    if (stream->dst.pitch != pitch) {
        mg_midi_chmsg2(output,
                MIDI_MSG_PITCH_BEND, stream->string->channel,
                MIDI_LSB(pitch), MIDI_MSB(pitch));
        stream->dst.pitch = pitch;
        return 3000;
    }

    return 0;
}

static int mg_output_midi_channel_pressure(struct mg_output *output, struct mg_stream *stream)
{
    int pressure = stream->string->model.pressure;

    if (stream->dst.pressure != pressure) {
        mg_midi_chmsg1(output, MIDI_MSG_CHANNEL_PRESSURE, stream->string->channel, pressure);
        stream->dst.pressure = pressure;
        return 2000;
    }

    return 0;
}

static int mg_output_midi_balance(struct mg_output *output, struct mg_stream *stream)
{
    int panning = stream->string->model.panning;

    if (stream->dst.panning != panning) {
        mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->string->channel, MG_CC_PANNING, panning);
        stream->dst.panning = panning;
        return 3000;
    }

    return 0;
}

static int mg_midi_chmsg1(struct mg_output *output, int msg, int channel, int val)
{
    uint8_t data[2];

    data[0] = msg | (channel & 0xF);
    data[1] = (val & 0x7F);

    return mg_midi_write(output, data, 2);
}

static int mg_midi_chmsg2(struct mg_output *output, int msg, int channel, int val1, int val2)
{
    uint8_t data[3];

    data[0] = msg | (channel & 0xF);
    data[1] = (val1 & 0x7F);
    data[2] = (val2 & 0x7F);

    return mg_midi_write(output, data, 3);
}

static int mg_midi_write(struct mg_output *output, uint8_t *buffer, size_t size)
{
    int ret;
    struct mg_midi_info *info = output->data;

    ret = write(info->fp, buffer, size);
    if (ret != size) {
        output->failed = 1;
        return -1;
    }

    return size;
}