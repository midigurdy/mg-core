#include <unistd.h>
#include <stdint.h>
#include "midi_lowlevel.h"
#include "utils.h"

static void mg_midi_out(struct mg_core *mg, uint8_t *buffer, size_t size);
static void mg_midi_16to14(uint16_t value, uint8_t *msb, uint8_t *lsb);

struct chstat {
    int on;
    int off;
    int cc;
    int pitch;
    int cp;
    int pp;
};

struct chmsg {
    int us;
    int type;
    int val1;
    int val2;
};

static struct chstat stats[9];
static struct timespec stats_time;
#define LOGLEN (1100)
static struct chmsg chlog[LOGLEN];
static int logpos = 0;

void doclog(int channel, int type, int val1, int val2)
{
    struct timespec now;
    int us;

    if (channel != 0) return;

    clock_gettime(CLOCK_MONOTONIC, &now);
    us = duration_us(stats_time, now);

    chlog[logpos].us = us;
    chlog[logpos].type = type;
    chlog[logpos].val1 = val1;
    chlog[logpos].val2 = val2;

    logpos++;
    if (logpos >= LOGLEN) {
        logpos = 0;
    }
}


void mg_midi_stats(void)
{
    int i;
    int ch_total;
    int total = 0;
    struct chstat *ch;
    struct timespec now;
    float us;

    clock_gettime(CLOCK_MONOTONIC, &now);
    us = duration_us(stats_time, now);
    clock_gettime(CLOCK_MONOTONIC, &stats_time);

    printf("=================\n");
    printf("Ch\tTOTAL\tOn\tOff\tCC\tPitch\tCP\tPP\n");
    for (i = 0; i < 9; i++) {
        ch = &stats[i];
        ch_total = ch->on + ch->off + ch->cc + ch->pitch + ch->cp + ch->pp;
        printf("%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
                i, ch_total,
                ch->on, ch->off, ch->cc, ch->pitch, ch->cp, ch->pp);
        total += ch_total;
    }
    printf("TOTAL: %d, ELAPSED ms: %f, msg/s: %f\n",
            total, us / 1000, total / (us / 1000000));

    for (i = 0; i < logpos; i++) {
        printf("%d\t", chlog[i].us);
        switch(chlog[i].type) {
            case 0:
                printf("on");
                break;
            case 1:
                printf("off");
                break;
            case 2:
                printf("cc");
                break;
            case 3:
                printf("pit");
                break;
            case 4:
                printf("cp");
                break;
            case 5:
                printf("pp");
                break;
            default:
                printf("??");
        }
        printf("\t%d\t%d\n", chlog[i].val1, chlog[i].val2);
    }

    memset(stats, 0, sizeof(stats));
    memset(chlog, 0, sizeof(chlog));
    logpos = 0;
}


void mg_midi_noteon(struct mg_core *mg, int channel, int note, int velocity)
{
    fluid_synth_noteon(mg->fluid, channel, note, velocity);
    stats[channel].on++;
    doclog(channel, 0, note, velocity);

    if (channel > 8) return;

    uint8_t data[3];
    data[0] = 0x90 | channel;
    data[1] = note;
    data[2] = velocity;
    mg_midi_out(mg, data, 3);
}

void mg_midi_noteoff(struct mg_core *mg, int channel, int note)
{
    fluid_synth_noteoff(mg->fluid, channel, note);
    stats[channel].off++;
    doclog(channel, 1, note, 0);

    if (channel > 8) return;

    uint8_t data[3];
    data[0] = 0x80 | channel;
    data[1] = note;
    data[2] = 0;
    mg_midi_out(mg, data, 3);
}

void mg_midi_all_notes_off(struct mg_core *mg, int channel)
{
    fluid_synth_all_notes_off(mg->fluid, channel);
}

void mg_midi_cc(struct mg_core *mg, int channel, int control, int value)
{
    fluid_synth_cc(mg->fluid, channel, control, value);
    stats[channel].cc++;
    doclog(channel, 2, control, value);

    if (channel > 8) return;

    uint8_t data[3];
    data[0] = 0xB0 | channel;
    data[1] = control;
    data[2] = value;
    mg_midi_out(mg, data, 3);
}

void mg_midi_pitch_bend(struct mg_core *mg, int channel, int pitch)
{
    fluid_synth_pitch_bend(mg->fluid, channel, pitch);
    stats[channel].pitch++;
    doclog(channel, 3, pitch, -1);
}

void mg_midi_channel_pressure(struct mg_core *mg, int channel, int pressure)
{
    fluid_synth_channel_pressure(mg->fluid, channel, pressure);
    stats[channel].cp++;
    doclog(channel, 4, pressure, -1);
}

void mg_midi_key_pressure(struct mg_core *mg, int channel, int note, int pressure)
{
    fluid_synth_key_pressure(mg->fluid, channel, note, pressure);
    stats[channel].pp++;
    doclog(channel, 5, note, pressure);
}

static void mg_midi_out(struct mg_core *mg, uint8_t *buffer, size_t size)
{
    int ret;

    if (mg->midi_out_fp < 0) {
        return;
    }

    ret = write(mg->midi_out_fp, buffer, size);
    if (ret != size) {
        printf("MIDI write returned %d\n", ret);
    }
}

static void mg_midi_16to14(uint16_t value, uint8_t *msb, uint8_t *lsb)
{
    uint16_t mask = 0x007F;  // low 7 bits on
    *lsb = value & mask;
    *msb = (value & (mask << 7)) >> 7;
}
