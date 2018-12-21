import cffi

ffibuilder = cffi.FFI()

ffibuilder.set_source(
    "mg.alsa._alsa", r"""

    #include <alsa/asoundlib.h>

    """,
    libraries=['asound'])


ffibuilder.cdef(r"""
    struct snd_ctl_t;
    struct snd_rawmidi_t;
    struct snd_rawmidi_info_t;

    int snd_card_next(int *card);
    int snd_ctl_open(struct snd_ctl_t *ctl[], const char *name, int mode);
    int snd_ctl_close(struct snd_ctl_t *ctl);
    int snd_ctl_rawmidi_next_device(struct snd_ctl_t *ctl, int *device);
    int snd_ctl_rawmidi_info(struct snd_ctl_t *ctl, struct snd_rawmidi_info_t * info);

    int snd_rawmidi_info_malloc(struct snd_rawmidi_info_t **info);
    void snd_rawmidi_info_free(struct snd_rawmidi_info_t *info);
    void snd_rawmidi_info_set_device(struct snd_rawmidi_info_t *info, unsigned int val);
    void snd_rawmidi_info_set_subdevice(struct snd_rawmidi_info_t *obj, unsigned int val);
    void snd_rawmidi_info_set_stream(struct snd_rawmidi_info_t *obj, int val);

    const char *snd_rawmidi_info_get_name(const struct snd_rawmidi_info_t *obj);
    const char *snd_rawmidi_info_get_subdevice_name(const struct snd_rawmidi_info_t *obj);

    int snd_rawmidi_open(struct snd_rawmidi_t **in_rmidi, struct snd_rawmidi_t **out_rmidi, const char *name, int mode);
    int snd_rawmidi_close(struct snd_rawmidi_t *rmidi);
    int snd_rawmidi_poll_descriptors_count(struct snd_rawmidi_t *rmidi);
    int snd_rawmidi_poll_descriptors(struct snd_rawmidi_t *rmidi, struct pollfd *pfds, unsigned int space);

    ssize_t snd_rawmidi_read(struct snd_rawmidi_t *rmidi, void *buffer, size_t size);

    const char *snd_strerror(int errnum);

    struct pollfd {
        int fd;
        short events;
        short revents;
    };
""")


if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
