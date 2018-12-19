#ifndef _MG_H_
#define _MG_H_

#include <poll.h>
#include <pthread.h>
#include <sys/prctl.h>

#include <fluidsynth.h>

#include "display.h"


#define KEY_COUNT (24)
#define NUM_NOTES (128)
#define MG_MAP_MAX_RANGES (20)

#define MG_WHEEL_REPORT_INTERVAL (10)

#define MG_MELODY_EXPRESSION_THRESHOLD (10)

#define MG_SPEED_MAX (5000)
#define MG_PRESSURE_MAX (3000)
#define MG_KEYVEL_MAX MG_PRESSURE_MAX

#define KEY_INACTIVE  (0)
#define KEY_ACTIVE  (1)

#define KEY_PRESSED (1)
#define KEY_RELEASED (2)

#define CHANNEL_OFF (-1)

#define MAX(a,b) (((a)>(b))?(a):(b))
#define MIN(a,b) (((a)<(b))?(a):(b))

#define MG_OUTPUT_COUNT (5)
#define MG_OUTPUT_FLUID (0)

#define MG_OUTPUT_STREAM_MAX (10)
#define MG_STREAM_SENDER_MAX (10)


#define MG_CC_VOLUME (7)
#define MG_CC_PANNING (8)  // uses balance control
#define MG_CC_EXPRESSION (11)
#define MG_CC_ALL_SOUNDS_OFF (0x78)
#define MG_CC_ALL_CTRL_OFF (0x79)


struct mg_output;
struct mg_stream;


/* Used to store variable mapping ranges */
struct mg_map {
    int ranges[MG_MAP_MAX_RANGES][2];
    int count;
};


/* Represents the (internal or external) state of a single note */
struct mg_note {
    int channel;  // -1 if note is off
    int velocity;
    int pressure;
};


/* Represents the (internal or external) state of a single string */
struct mg_voice {
    int expression;
    int pitch;
    int volume;
    int panning;
    int pressure;

    struct mg_note notes[NUM_NOTES];
    int active_notes[NUM_NOTES];
    int note_count;
};


/* Callback that gets called before an output is removed from the core. */
typedef void (mg_output_close_t)(struct mg_output *output);

/* Callback functions to write note on and off messages to an output. They should return
 * the number of tokens required to write the messages. */
typedef int (mg_output_noteon_t)(struct mg_output *output, int channel, int note, int velocity);
typedef int (mg_output_noteoff_t)(struct mg_output *output, int channel, int note);
typedef int (mg_output_reset_t)(struct mg_output *output, int channel);

/* Callback functions that take care of syncing the mg_voice value with the output. They
 * should compare the attribute they are interesting in on src and dst, only write
 * to the output if those numbers differ and update the dst structure after a new value
 * was sent. If a transfer occured, return the number of tokens used during that transfer, or 0 if
 * no data was transmitted. */
typedef int (mg_output_send_t)(struct mg_output *output, struct mg_stream *stream);


struct mg_stream {
    struct mg_string *string;
    struct mg_voice dst;

    /* For rate limiting */
    int tokens; /* the current contents of the token bucket */
    int max_tokens; /* maximal number of tokens allowed in the bucket */
    int tokens_percent; /* percentage of tokens that this stream received on each tick */
    int tokens_per_tick; /* pre-calculated number of tokens this stream received on each tick */

    /* List of message sender callbacks that handle all messages except note on / off */
    mg_output_send_t *sender[MG_STREAM_SENDER_MAX];
    int sender_count;
    int sender_idx; /* round-robin message sending index */

    int enabled;
};


struct mg_output {
    int id;

    struct mg_stream *stream[MG_OUTPUT_STREAM_MAX];
    int stream_count;

    /* Total number of tokens added to the (enabled) stream buckets per tick.
     * Set to 0 to disable rate-limiting. */
    int tokens_per_tick;

    int enabled;
    int failed;

    /* callbacks that actually write to the output streams */
    mg_output_noteon_t *noteon;
    mg_output_noteoff_t *noteoff;
    mg_output_reset_t *reset;

    /* Optional callback to close an output and do any cleanup tasks */
    mg_output_close_t *close;

    void *data; /* optional output private data */
};


/* Combines two mg_voice structs to record the internal and external state of a
 * single string. The modelling keeps the internal view of the string in
 * 'model', the external (synth) state in 'synth'. The difference between model
 * and synth state is used to determine which messages to send to the synth.
 */
struct mg_string {
    int channel; /* MIDI channel */

    int base_note;
    int muted;
    int volume;
    int panning;

    int base_note_count;

    int mode;

    /* only used on melody string */
    int polyphonic;
    int empty_key; /* used to implement "capos" on melody strings */

    /* only used on trompette strings */
    int threshold;
    int attack;

    /* only used on trompette and drone strings */
    int fixed_notes[NUM_NOTES];
    int fixed_note_count;

    /* the intended state of the synthesizer voice, output streams
     * reference and read this structure but will never modify it */
    struct mg_voice model;
};

/* The internal and external state of the instrument. Contains the collection of
 * all available strings in the instrument. Many of the state values can be set
 * by the Python program, so protect the whole structure with a single mutex.
 *
 * TODO: If the internal modelling holds the mutex for too long, maybe switch
 * over to to separate mutexes per string.  */

struct mg_state {
    struct mg_string melody[3];
    struct mg_string drone[3];
    struct mg_string trompette[3];
    struct mg_string keynoise;

    float pitchbend_factor;

    int key_on_debounce;
    int key_off_debounce;
    int base_note_delay;

    struct mg_map pressure_to_poly;
    struct mg_map pressure_to_pitch;
    struct mg_map speed_to_melody_volume;
    struct mg_map speed_to_drone_volume;
    struct mg_map speed_to_trompette_volume;
    struct mg_map speed_to_chien;
    struct mg_map keyvel_to_notevel;
    struct mg_map keyvel_to_tangent;
    struct mg_map keyvel_to_keynoise;

    pthread_mutex_t mutex; /* protects access to this structure */
};


/* The current state of the wheel sensor */
struct mg_wheel {
    /* current position of the wheel as a 14 bit number */
    unsigned int position;

    /* distance the wheel has travelled since the previous reading,
     * positive values means the wheel is turning forward, negative values
     * backwards */
    int distance;

    /* Number of microseconds in which the wheel has travelled the above
     * distance. Only valid if distance > 0 */
    unsigned int elapsed_us;

    /* last distance reading. As distance might be a combination of multiple
     * wheel events, we use this value to determine if the wheel is actually
     * stationary. */
    int last_distance;

    /* diagnostic data: the virtual gain set by the wheel sensor. used for
     * calibrating the distance of the magnet from the sensor chip */
    unsigned int gain;

    /* current speed of the wheel */
    unsigned int speed;

    /* accelleration (positive) or decelleration (negative) of wheel speed */
    unsigned int accel;
};


/* State for a single keyboard key */
struct mg_key {
    /* sensor readings from kernel driver */
    int raw_pressure;
    int pressure;
    int max_pressure;
    int smoothed_pressure;

    /* internally calculated from sensor readings */
    int velocity;
    int state;  // current state of key: active or inactive
    int action; // if the key has changed state since last reading 
    int active_since;

    int debounce; // only used for debouncing
};


struct mg_key_calib {
    float pressure_adjust;
    float velocity_adjust;
};


/* Internal structure of the current state and configuration of the core.
 * Gets passed to all threads.
 * */
struct mg_core {
    /* worker thread and return value */
    pthread_t worker_pth;
    int worker_retval;

    /* server thread and return value */
    pthread_t server_pth;
    int server_retval;
    int server_client_count;
    struct lws_context *websocket_ctx;

    /* notifies thread to terminate */
    int should_stop;

    int halt_midi_output;

    /* notifies worker thread that initialization is finished and that it
     * can start doing it's work */
    int started;

    /* created by Python program and passed when starting the core */
    fluid_synth_t *fluid;

    /* list of midi outputs */
    struct mg_output *outputs[MG_OUTPUT_COUNT];
    int output_count;

    /* protects access to the fields above */
    pthread_mutex_t mutex;

    struct mg_state state;

    /* the poll file descriptors for wheel and key input devices */
    struct pollfd sensor_fds[2];
    int sensor_fd_count;

    /* wheel sensor data */
    struct mg_wheel wheel;

    /* key sensor data */
    struct mg_key keys[KEY_COUNT];

    /* key calibration data */
    struct mg_key_calib key_calib[KEY_COUNT];

    int chien_volume;
    int chien_speed;

    int initialized;
};


#define WORKER_PRIO (50)
#define WORKER_INTERVAL_US (1000)

#define MIDI_DEBUG 0

#define EMPTY_NOTE_DELAY 50
#define TICKS_PER_SECOND 2000

#define NUM_CHANNELS 3

#define CHIEN_MAX_VAL 100
#define NOTEOFF -9999
#define MIDIDEV "hw:1,0,0"

#define NSEC_PER_SEC    (1000000000) /* The number of nsecs per sec. */


/* Public API */
enum mg_mode_enum {
    MG_MODE_MIDIGURDY,
    MG_MODE_GENERIC,
    MG_MODE_KEYBOARD,
};

enum mg_string_enum {
    MG_MELODY1,
    MG_MELODY2,
    MG_MELODY3,
    MG_TROMPETTE1,
    MG_TROMPETTE2,
    MG_TROMPETTE3,
    MG_DRONE1,
    MG_DRONE2,
    MG_DRONE3,
    MG_KEYNOISE
};

enum mg_param_enum {
    MG_PARAM_END, /* sentinel */

    MG_PARAM_MUTE,
    MG_PARAM_VOLUME,
    MG_PARAM_CHANNEL,
    MG_PARAM_BASE_NOTE,
    MG_PARAM_PANNING,

    /* melody voice only */
    MG_PARAM_POLYPHONIC,
    MG_PARAM_EMPTY_KEY,

    /* trompette voice only */
    MG_PARAM_THRESHOLD,
    MG_PARAM_ATTACK,

    MG_PARAM_NOTE_ENABLE,
    MG_PARAM_NOTE_DISABLE,
    MG_PARAM_NOTE_CLEAR,
    MG_PARAM_RESET,
    MG_PARAM_MODE,
};

enum mg_map_enum {
    MG_MAP_PRESSURE_TO_POLY,
    MG_MAP_PRESSURE_TO_PITCH,
    MG_MAP_SPEED_TO_MELODY_VOLUME,
    MG_MAP_SPEED_TO_DRONE_VOLUME,
    MG_MAP_SPEED_TO_TROMPETTE_VOLUME,
    MG_MAP_SPEED_TO_CHIEN,
    MG_MAP_KEYVEL_TO_NOTEVEL,
    MG_MAP_KEYVEL_TO_TANGENT,
    MG_MAP_KEYVEL_TO_KEYNOISE,
};

struct mg_string_config {
    int string;
    int param;
    int val;
};

extern int mg_initialize();
extern int mg_start(fluid_synth_t *fluid);
extern int mg_stop(void);
extern int mg_halt_midi_output(int halted);

extern int mg_set_pitchbend_factor(float factor);
extern int mg_set_key_on_debounce(int num);
extern int mg_set_key_off_debounce(int num);
extern int mg_set_base_note_delay(int num);
extern int mg_set_string(struct mg_string_config *configs);
extern int mg_get_wheel_gain(void);
extern int mg_get_mapping(struct mg_map *dst, int idx);
extern int mg_set_mapping(const struct mg_map *src, int idx);
extern int mg_reset_mapping_ranges(int idx);

extern int mg_add_midi_output(const char *device);
extern int mg_remove_midi_output(int output_id);

struct mg_image {
    char *filename;
    int width;
    int height;
    int size;
    char *data;
    struct mg_image_ft ft;
    char *membuf;

    pthread_mutex_t mutex;

    char *scroll_data;
    int scroll_enable;
    int scroll_x;
    int scroll_y;
    int scroll_width;
    int scroll_height;
    char *scroll_text;
    int scroll_text_width;
    int scroll_offset;
    int scroll_end_delay_ms;
    pthread_t scroll_pth;
    int scroll_timerfd;
    int scroll_step;
};


extern struct mg_image *mg_image_create(int width, int height, const char *filename);
extern int mg_image_mmap_file(struct mg_image *img, const char *filename);
extern void mg_image_destroy(struct mg_image *img);
extern void mg_image_clear(struct mg_image *img, int x0, int y0, int x1, int y1);
extern void mg_image_line(struct mg_image *img, int x0, int y0, int x1, int y1, int c);
extern void mg_image_point(struct mg_image *img, int x, int y, int c);
extern char *mg_image_data(struct mg_image *img);
extern int mg_image_load_font(struct mg_image *img, const char *filename);
extern void mg_image_puts(struct mg_image *img, int face_id,
        const char *text, int x, int y, int color,
        int line_spacing, int align, int anchor,
        int max_width, int x_offset);
extern void mg_image_scrolltext(struct mg_image *img, int face_id, const char *text,
        int x, int y, int width, int color,
        int initial_delay_ms, int shift_delay_ms, int end_delay_ms);

extern void mg_image_rect(struct mg_image *img, int x0, int y0, int x1, int y1,
        int c, int fill);
extern int mg_image_write(struct mg_image *img, const char *filename);

extern int mg_calibrate_set_key(int key, float pressure_adjust, float velocity_adjust);
extern int mg_calibrate_get_key(int key, float *pressure_adjust, float *velocity_adjust);

#endif
