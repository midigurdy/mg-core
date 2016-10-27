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
    int filter_cutoff;
    int filter_resonance;

    struct mg_note notes[NUM_NOTES];
    int active_notes[NUM_NOTES];
    int note_count;
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

    /* the intended state of the synthesizer voice */
    struct mg_voice model;

    /* the current state of the synthesizer voice */
    struct mg_voice synth;
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

    /* key sensor data with higher debounce count */
    struct mg_key slow_keys[KEY_COUNT];

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


struct mg_image {
    int width;
    int height;
    int size;
    char *data;
    struct mg_image_ft ft;
    char *membuf;
};


extern struct mg_image *mg_image_create(int width, int height);
extern int mg_image_mmap_file(struct mg_image *img, const char *filename);
extern void mg_image_destroy(struct mg_image *img);
extern void mg_image_clear(struct mg_image *img);
extern void mg_image_line(struct mg_image *img, int x0, int y0, int x1, int y1, int c);
extern void mg_image_point(struct mg_image *img, int x, int y, int c);
extern char *mg_image_data(struct mg_image *img);
extern int mg_image_load_font(struct mg_image *img, const char *filename);
extern void mg_image_puts(struct mg_image *img, int face_id,
        const char *text, int x, int y, int color,
        int line_spacing, int align, int anchor,
        int max_width, int x_offset);

extern void mg_image_rect(struct mg_image *img, int x0, int y0, int x1, int y1,
        int c, int fill);
extern int mg_image_write(struct mg_image *img, const char *filename);

extern int mg_calibrate_set_key(int key, float pressure_adjust, float velocity_adjust);
extern int mg_calibrate_get_key(int key, float *pressure_adjust, float *velocity_adjust);

#endif
