import cffi

ffibuilder = cffi.FFI()

ffibuilder.set_source(
    "mg.fluidsynth._fluidsynth",
    r"""
        #include "fluidsynth.h"
    """,
    libraries=['fluidsynth']
)

ffibuilder.cdef("""
typedef struct _fluid_audio_driver_t fluid_audio_driver_t;
typedef struct _fluid_hashtable_t fluid_settings_t;
typedef struct _fluid_synth_t fluid_synth_t;
typedef struct _fluid_midi_event_t fluid_midi_event_t;
typedef struct _fluid_voice_t fluid_voice_t;
typedef struct _fluid_ladspa_fx_t fluid_ladspa_fx_t;

enum fluid_types_enum {
         FLUID_NO_TYPE = -1,
         FLUID_NUM_TYPE,
         FLUID_INT_TYPE,
         FLUID_STR_TYPE,
         FLUID_SET_TYPE
};

#define FLUID_FAILED -1
#define FLUID_OK 0

fluid_settings_t* new_fluid_settings(void);
void delete_fluid_settings(fluid_settings_t* settings);

fluid_synth_t* new_fluid_synth(fluid_settings_t* settings);
void  delete_fluid_synth(fluid_synth_t* synth);

fluid_audio_driver_t* new_fluid_audio_driver(fluid_settings_t* settings, fluid_synth_t* synth);
void delete_fluid_audio_driver(fluid_audio_driver_t* driver);

int fluid_synth_sfload(fluid_synth_t* synth, const char* filename, int reset_presets);
int fluid_synth_sfunload(fluid_synth_t* synth, unsigned int id, int reset_presets);

int fluid_settings_get_type(fluid_settings_t* settings, const char *name);
int fluid_settings_setstr(fluid_settings_t* settings, const char *name, const char *str);
int fluid_settings_setnum(fluid_settings_t* settings, const char *name, double val);
int fluid_settings_setint(fluid_settings_t* settings, const char *name, int val);

int fluid_synth_noteon(fluid_synth_t* synth, int chan, int key, int vel);
int fluid_synth_noteoff(fluid_synth_t* synth, int chan, int key);
int fluid_synth_cc(fluid_synth_t* synth, int chan, int ctrl, int val);


int fluid_synth_pitch_wheel_sens(fluid_synth_t* synth, int chan, int val);
int fluid_synth_program_select(fluid_synth_t* synth, int chan, unsigned int sfont_id,
                               unsigned int bank_num, unsigned int preset_num);
int fluid_synth_unset_program (fluid_synth_t *synth, int chan);

int fluid_synth_pin_preset(fluid_synth_t *synth, int sfont_id, int bank_num, int preset_num);
int fluid_synth_unpin_preset(fluid_synth_t *synth, int sfont_id, int bank_num, int preset_num);

void fluid_synth_set_reverb(fluid_synth_t* synth, double roomsize,
                            double damping, double width, double level);
void fluid_synth_set_reverb_on(fluid_synth_t* synth, int on);

void fluid_synth_set_gain(fluid_synth_t* synth, float gain);
float fluid_synth_get_gain(fluid_synth_t* synth);

double fluid_synth_get_cpu_load(fluid_synth_t* synth);


typedef int (*handle_midi_event_func_t)(void* data, fluid_midi_event_t* event);

int fluid_synth_handle_midi_event(void* data, fluid_midi_event_t* event);

enum fluid_log_level {
  FLUID_PANIC,
  FLUID_ERR,
  FLUID_WARN,
  FLUID_INFO,
  FLUID_DBG,
  LAST_LOG_LEVEL
};

typedef void (*fluid_log_function_t)(int level, char* message, void* data);
fluid_log_function_t fluid_set_log_function(int level, fluid_log_function_t fun, void* data);
void fluid_default_log_function(int level, char* message, void* data);

int fluid_synth_sfcount(fluid_synth_t* synth);

fluid_ladspa_fx_t *fluid_synth_get_ladspa_fx(fluid_synth_t *synth);

int fluid_ladspa_is_active(fluid_ladspa_fx_t *fx);
int fluid_ladspa_activate(fluid_ladspa_fx_t *fx);
int fluid_ladspa_deactivate(fluid_ladspa_fx_t *fx);
int fluid_ladspa_reset(fluid_ladspa_fx_t *fx);
int fluid_ladspa_check(fluid_ladspa_fx_t *fx, char *err, int err_size);
int fluid_ladspa_add_effect(fluid_ladspa_fx_t *fx, const char *effect_name, const char *lib_name, const char *plugin_name);
int fluid_ladspa_effect_set_mix(fluid_ladspa_fx_t *fx, const char *name, int mix, float gain);
int fluid_ladspa_effect_set_control(fluid_ladspa_fx_t *fx, const char *effect_name, const char *port_name, float val);
int fluid_ladspa_effect_link(fluid_ladspa_fx_t *fx, const char *effect_name, const char *port_name, const char *name);
int fluid_ladspa_add_buffer(fluid_ladspa_fx_t *fx, const char *name);


""")
