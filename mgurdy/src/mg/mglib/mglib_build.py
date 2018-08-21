import cffi

ffibuilder = cffi.FFI()

ffibuilder.set_source(
    "mg.mglib._mglib",
    r"""
        #include "fluidsynth.h"
        #include "mg.h"
    """,
    libraries=['mgurdy', 'fluidsynth'])

ffibuilder.cdef(r"""
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

#define MG_MAP_MAX_RANGES 20

struct mg_map {
    int ranges[MG_MAP_MAX_RANGES][2];
    int count;
};

struct mg_string_config {
    int string;
    int param;
    int val;
};

int mg_initialize();
int mg_start(void *synth);
int mg_stop(void);
int mg_halt_midi_output(int halted);

int mg_set_pitchbend_factor(float factor);
int mg_set_key_on_debounce(int num);
int mg_set_key_off_debounce(int num);
int mg_set_base_note_delay(int num);
int mg_set_string(struct mg_string_config *configs);
int mg_get_wheel_gain(void);
int mg_get_mapping(struct mg_map *dst, int idx);
int mg_set_mapping(const struct mg_map *src, int idx);
int mg_reset_mapping_ranges(int idx);

struct mg_image;

struct mg_image *mg_image_create(int width, int height, const char *filename);
int mg_image_mmap_file(struct mg_image *img, const char *filename);
void mg_image_destroy(struct mg_image *img);
void mg_image_clear(struct mg_image *img, int x0, int y0, int x1, int y1);
void mg_image_line(struct mg_image *img, int x0, int y0, int x1, int y1, int c);
void mg_image_point(struct mg_image *img, int x, int y, int c);
char *mg_image_data(struct mg_image *img);
int mg_image_load_font(struct mg_image *img, char *filename);
void mg_image_puts(struct mg_image *img, int face_id,
                   const char *text, int x, int y, int color,
                   int line_spacing, int align, int anchor,
                   int max_width, int x_offset);
void mg_image_rect(struct mg_image *img, int x0, int y0, int x1, int y1,
                   int c, int fill);
int mg_image_write(struct mg_image *img, const char *filename);
void mg_image_scrolltext(struct mg_image *img, int face_id, const char *text,
        int x, int y, int width, int color,
        int initial_delay_ms, int shift_delay_ms, int end_delay_ms);

int mg_calibrate_set_key(int key, float pressure_adjust,
                         float velocity_adjust);
int mg_calibrate_get_key(int key, float *pressure_adjust,
                        float *velocity_adjust);

""")

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
