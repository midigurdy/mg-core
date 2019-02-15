#include <stdint.h>
#include <alsa/asoundlib.h>

#include "output_midi.h"
#include "output.h"


static int add_melody_stream(struct mg_output *output, struct mg_string *string, int tokens_percent, int channel);
static int add_trompette_stream(struct mg_output *output, struct mg_string *string, int tokens_percent, int channel);
static int add_drone_stream(struct mg_output *output, struct mg_string *string, int tokens_percent, int channel);

static void mg_output_midi_close(struct mg_output *output);

static int mg_output_midi_noteon(struct mg_output *output, int channel, int note, int velocity);
static int mg_output_midi_noteoff(struct mg_output *output, int channel, int note);
static int mg_output_midi_reset(struct mg_output *output, int channel);

static int mg_output_midi_expression(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_volume(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_pitch(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_channel_pressure(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_balance(struct mg_output *output, struct mg_stream *stream);
static int mg_output_midi_bank_prog(struct mg_output *output, struct mg_stream *stream);

static int mg_midi_chmsg1(struct mg_output *output, int msg, int channel, int val);
static int mg_midi_chmsg2(struct mg_output *output, int msg, int channel, int val1, int val2);
static int mg_midi_write(struct mg_output *output, uint8_t *buffer, size_t size);


#define MIDI_LSB(val) (val & 0x7F)
#define MIDI_MSB(val) ((val & (0x7F << 7)) >> 7)

#define MIDI_MSG_NOTEON                (0x90)
#define MIDI_MSG_NOTEOFF               (0x80)
#define MIDI_MSG_CONTROL_CHANGE        (0xB0)
#define MIDI_MSG_PROGRAM_CHANGE        (0xC0)
#define MIDI_MSG_CHANNEL_PRESSURE      (0xD0)
#define MIDI_MSG_POLY_PRESSURE         (0xA0)
#define MIDI_MSG_PITCH_BEND            (0xE0)


struct mg_midi_info {
    snd_rawmidi_t *rawmidi;
    char *device;
};


struct mg_output *new_midi_output(struct mg_core *mg, const char *device)
{
    struct mg_output *output;
    struct mg_midi_info *info;
    snd_rawmidi_t *rawmidi;
    int err;

    err = snd_rawmidi_open(NULL, &rawmidi, device, SND_RAWMIDI_NONBLOCK);
    if (err) {
        fprintf(stderr, "Error opening raw MIDI device %s: %s\n",
                device, snd_strerror(err));
        return NULL;
    }
    
    output = mg_output_new();
    if (output == NULL) {
        snd_rawmidi_close(rawmidi);
        return NULL;
    }

    info = malloc(sizeof(struct mg_midi_info));
    if (info == NULL) {
        snd_rawmidi_close(rawmidi);
        mg_output_delete(output);
        return NULL;
    }

    info->rawmidi = rawmidi;
    info->device = strdup(device);
    if (info->device == NULL) {
        fprintf(stderr, "Out of memory\n");
        snd_rawmidi_close(rawmidi);
        mg_output_delete(output);
        return NULL;
    }

    output->data = info;
    output->close = mg_output_midi_close;
    output->noteon = mg_output_midi_noteon;
    output->noteoff = mg_output_midi_noteoff;
    output->reset = mg_output_midi_reset;
    output->tokens_per_tick = 3000;

    if (!(add_melody_stream(output, &mg->state.melody[0], 60, 0) &&
          add_trompette_stream(output, &mg->state.trompette[0], 30, 1) &&
          add_drone_stream(output, &mg->state.drone[0], 10, 2)))
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

    snd_rawmidi_drop(info->rawmidi);
    snd_rawmidi_close(info->rawmidi);
    free(info->device);
    free(info);

    output->data = NULL;
}


static int add_melody_stream(struct mg_output *output, struct mg_string *string, int tokens_percent, int channel)
{
    struct mg_stream *stream = mg_output_stream_new(string, tokens_percent, channel);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_midi_expression;
    stream->sender[stream->sender_count++] = mg_output_midi_pitch;
    stream->sender[stream->sender_count++] = mg_output_midi_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_midi_volume;
    stream->sender[stream->sender_count++] = mg_output_midi_balance;
    stream->sender[stream->sender_count++] = mg_output_midi_bank_prog;

    output->stream[output->stream_count++] = stream;

    stream->max_tokens = 9000;

    return 1;
}

static int add_trompette_stream(struct mg_output *output, struct mg_string *string, int tokens_percent, int channel)
{
    struct mg_stream *stream = mg_output_stream_new(string, tokens_percent, channel);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_midi_expression;
    stream->sender[stream->sender_count++] = mg_output_midi_channel_pressure;
    stream->sender[stream->sender_count++] = mg_output_midi_volume;
    stream->sender[stream->sender_count++] = mg_output_midi_balance;
    stream->sender[stream->sender_count++] = mg_output_midi_bank_prog;

    output->stream[output->stream_count++] = stream;

    stream->max_tokens = 9000;

    return 1;
}

static int add_drone_stream(struct mg_output *output, struct mg_string *string, int tokens_percent, int channel)
{
    struct mg_stream *stream = mg_output_stream_new(string, tokens_percent, channel);
    if (stream == NULL) {
        return 0;
    }

    stream->sender[stream->sender_count++] = mg_output_midi_expression;
    stream->sender[stream->sender_count++] = mg_output_midi_volume;
    stream->sender[stream->sender_count++] = mg_output_midi_balance;
    stream->sender[stream->sender_count++] = mg_output_midi_bank_prog;

    output->stream[output->stream_count++] = stream;

    stream->max_tokens = 9000;

    return 1;
}

static int mg_output_midi_noteon(struct mg_output *output, int channel, int note, int velocity)
{
    if (mg_midi_chmsg2(output, MIDI_MSG_NOTEON, channel, note, velocity)) {
        return -1;
    }
    return 3000;
}

static int mg_output_midi_noteoff(struct mg_output *output, int channel, int note)
{
    if (mg_midi_chmsg2(output, MIDI_MSG_NOTEOFF, channel, note, 0)) {
        return -1;
    }
    return 3000;
}

static int mg_output_midi_reset(struct mg_output *output, int channel)
{
    if (mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, channel, MG_CC_ALL_SOUNDS_OFF, 0)) {
        return -1;
    }
    if (mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, channel, MG_CC_ALL_CTRL_OFF, 0)) {
        return -1;
    }
    return 6000;
}

static int mg_output_midi_expression(struct mg_output *output, struct mg_stream *stream)
{
    int expression = stream->string->model.expression;
    if (expression == 0) {
        expression = 1;
    }

    if (stream->dst.expression != expression) {
        if (mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->channel, MG_CC_EXPRESSION, expression)) {
            return -1;
        }
        stream->dst.expression = expression;
        return 3000;
    }

    return 0;
}

static int mg_output_midi_volume(struct mg_output *output, struct mg_stream *stream)
{
    // volume taken directly from string, no modelling involved
    int volume = stream->string->volume;

    if (stream->dst.volume != volume) {
        if (mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->channel, MG_CC_VOLUME, volume)) {
            return -1;
        }
        stream->dst.volume = volume;
        return 3000;
    }

    return 0;
}

static int mg_output_midi_pitch(struct mg_output *output, struct mg_stream *stream)
{
    int pitch = stream->string->model.pitch;

    if (stream->dst.pitch != pitch) {
        if (mg_midi_chmsg2(output, MIDI_MSG_PITCH_BEND, stream->channel, MIDI_LSB(pitch), MIDI_MSB(pitch))) {
            return -1;
        }
        stream->dst.pitch = pitch;
        return 3000;
    }

    return 0;
}

static int mg_output_midi_channel_pressure(struct mg_output *output, struct mg_stream *stream)
{
    int pressure = stream->string->model.pressure;

    if (stream->dst.pressure != pressure) {
        if (mg_midi_chmsg1(output, MIDI_MSG_CHANNEL_PRESSURE, stream->channel, pressure)) {
            return -1;
        }
        stream->dst.pressure = pressure;
        return 2000;
    }

    return 0;
}

static int mg_output_midi_balance(struct mg_output *output, struct mg_stream *stream)
{
    // panning taken directly from string, no modelling involved
    int panning = stream->string->panning;

    if (stream->dst.panning != panning) {
        if (mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->channel, MG_CC_PANNING, panning)) {
            return -1;
        }
        stream->dst.panning = panning;
        return 3000;
    }

    return 0;
}

static int mg_output_midi_bank_prog(struct mg_output *output, struct mg_stream *stream)
{
    // bank and prog taken directly from string, no modelling involved
    int bank = stream->string->bank;
    int program = stream->string->program;
    int tokens = 0;

    if (!output->send_prog_change) {
        return 0;
    }

    if (stream->dst.bank != bank) {
        if (mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->channel, MG_CC_BANK_LSB, MIDI_LSB(bank))) {
            return -1;
        }
        if (mg_midi_chmsg2(output, MIDI_MSG_CONTROL_CHANGE, stream->channel, MG_CC_BANK_MSB, MIDI_MSB(bank))) {
            return -1;
        }
        stream->dst.bank = bank;
        tokens += 6000;
    }

    if (stream->dst.program != program) {
        if (mg_midi_chmsg1(output, MIDI_MSG_PROGRAM_CHANGE, stream->channel, program)) {
            return -1;
        }
        stream->dst.program = program;
        tokens += 2000;
    }

    return tokens;
}

static int mg_midi_chmsg1(struct mg_output *output, int msg, int channel, int val)
{
    uint8_t data[2];

    data[0] = msg | (channel & 0xF);
    data[1] = (val & 0x7F);

    return (mg_midi_write(output, data, 2) == 2) ? 0 : -1;
}

static int mg_midi_chmsg2(struct mg_output *output, int msg, int channel, int val1, int val2)
{
    uint8_t data[3];

    data[0] = msg | (channel & 0xF);
    data[1] = (val1 & 0x7F);
    data[2] = (val2 & 0x7F);

    return (mg_midi_write(output, data, 3) == 3) ? 0 : -1;
}

static int mg_midi_write(struct mg_output *output, uint8_t *buffer, size_t size)
{
    size_t ret;
    struct mg_midi_info *info = output->data;

    ret = snd_rawmidi_write(info->rawmidi, buffer, size);
    if (ret != size) {
        fprintf(stderr, "rawmidi write failed on %s: %s\n", info->device,
                (ret < 0) ? snd_strerror(ret): "unknown error");
        return -1;
    }

    return size;
}
