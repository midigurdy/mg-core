from errno import EAGAIN

from ._alsa import lib, ffi

RAWMIDI_OUTPUT_STREAM = 0
RAWMIDI_INPUT_STREAM = 1

RAWMIDI_NONBLOCK = 2


class RawMIDI:
    def get_ports(self):
        ports = []

        card_idx = ffi.new('int *', -1)
        while True:
            if lib.snd_card_next(card_idx) != 0:
                raise RuntimeError('Unable to get alsa card')
            if card_idx[0] == -1:
                break
            ports.extend(self.get_card_ports(card_idx[0]))

        return ports

    def get_card_ports(self, card_idx):
        ports = []

        card_id = 'hw:%d' % card_idx
        ctl = ffi.new('struct snd_ctl_t **')
        if lib.snd_ctl_open(ctl, card_id.encode(), 0) != 0:
            raise RuntimeError('Unable to open control for card %s' % card_id)
        try:
            device_idx = ffi.new('int *', -1)
            while True:
                if lib.snd_ctl_rawmidi_next_device(ctl[0], device_idx) != 0:
                    raise RuntimeError('Unable to get new rawmidi device')
                if device_idx[0] == -1:
                    break
                ports.extend(self.get_device_ports(ctl[0], card_idx, device_idx[0]))
        finally:
            lib.snd_ctl_close(ctl[0])

        return ports

    def get_device_ports(self, ctl, card_idx, device_idx):
        ports = []

        info = ffi.new('struct snd_rawmidi_info_t **')
        if lib.snd_rawmidi_info_malloc(info) != 0:
            raise RuntimeError('Unable to malloc rawmidi info struct')
        subdevice_idx = 0
        try:
            while True:
                lib.snd_rawmidi_info_set_device(info[0], device_idx)
                lib.snd_rawmidi_info_set_subdevice(info[0], subdevice_idx)
                if lib.snd_ctl_rawmidi_info(ctl, info[0]) != 0:
                    break
                device_name_ffi = lib.snd_rawmidi_info_get_name(info[0])
                device_name = ffi.string(device_name_ffi).decode()
                subdevice_name_ffi = lib.snd_rawmidi_info_get_subdevice_name(info[0])
                subdevice_name = ffi.string(subdevice_name_ffi).decode()

                port = RawMIDIPort(
                    card_idx, device_idx, subdevice_idx,
                    subdevice_name or device_name,
                    self.port_is_input(ctl, device_idx, subdevice_idx),
                    self.port_is_output(ctl, device_idx, subdevice_idx)
                )
                ports.append(port)
                subdevice_idx += 1
        finally:
            lib.snd_rawmidi_info_free(info[0])

        return ports

    def port_is_input(self, ctl, device_idx, subdevice_idx):
        return self.port_is_stream(ctl, device_idx, subdevice_idx, RAWMIDI_INPUT_STREAM)

    def port_is_output(self, ctl, device_idx, subdevice_idx):
        return self.port_is_stream(ctl, device_idx, subdevice_idx, RAWMIDI_OUTPUT_STREAM)

    def port_is_stream(self, ctl, device_idx, subdevice_idx, stream):
        info = ffi.new('struct snd_rawmidi_info_t **')
        if lib.snd_rawmidi_info_malloc(info) != 0:
            raise RuntimeError('Unable to malloc rawmidi info struct')
        try:
            lib.snd_rawmidi_info_set_device(info[0], device_idx)
            lib.snd_rawmidi_info_set_subdevice(info[0], subdevice_idx)
            lib.snd_rawmidi_info_set_stream(info[0], stream)
            return lib.snd_ctl_rawmidi_info(ctl, info[0]) == 0
        finally:
            lib.snd_rawmidi_info_free(info[0])


class RawMIDIPort:
    def __init__(self, card_idx, device_idx, subdevice_idx,
                 name, is_input=True, is_output=True):
        self.card_idx = card_idx
        self.device_idx = device_idx
        self.subdevice_idx = subdevice_idx
        self.device = 'hw:{},{},{}'.format(card_idx, device_idx, subdevice_idx)
        self.name = name
        self.id = '{}-{}'.format(self.device, self.name)
        self.is_input = is_input
        self.is_output = is_output

        self.rmidi = None
        self.pollfds = None

    def __repr__(self):
        return '<{} "{}" ({}{})>'.format(
            self.device,
            self.name,
            'I' if self.is_input else '',
            'O' if self.is_output else '')

    def open(self, mode, nonblock=True):
        if self.rmidi:
            raise IOError('MIDI port {} already opened!'.format(self.device))

        if mode == 'r':
            in_rmidi = ffi.new('struct snd_rawmidi_t **')
            out_rmidi = ffi.NULL
        else:
            in_rmidi = ffi.NULL
            out_rmidi = ffi.new('struct snd_rawmidi_t **')

        block = RAWMIDI_NONBLOCK if nonblock else 0

        ret = lib.snd_rawmidi_open(in_rmidi, out_rmidi, self.device.encode(), block)
        if ret != 0:
            raise IOError('Unable to open MIDI port {}: {}'.format(
                self.device,
                ffi.string(lib.snd_strerror(ret)).decode()
            ))

        self.rmidi = in_rmidi if mode == 'r' else out_rmidi

        return self

    def close(self):
        if self.rmidi:
            if lib.snd_rawmidi_close(self.rmidi[0]) != 0:
                raise IOError('Unable to close MIDI port {}'.format(self.device))
        self.pollfds = None
        self.rmidi = None

    def read(self, size):
        buf = ffi.new('unsigned char[{}]'.format(size))
        ret = lib.snd_rawmidi_read(self.rmidi[0], buf, size)
        if ret < 0:
            if ret == -EAGAIN:
                return []
            raise IOError('Read on MIDI port returned error {}: {}'.format(
                ret,
                ffi.string(lib.snd_strerror(ret)).decode()
            ))
        return bytes(buf[0:ret])

    def fileno(self):
        if self.rmidi is None:
            raise IOError('Open MIDI device first!')
        if self.pollfds is None:
            fdcount = lib.snd_rawmidi_poll_descriptors_count(self.rmidi[0])
            if fdcount != 1:
                raise IOError('Descriptor count is {} for {}'.format(fdcount, self.device))
            pfds = ffi.new('struct pollfd *')
            if lib.snd_rawmidi_poll_descriptors(self.rmidi[0], pfds, 1) != 1:
                raise IOError('Unable to get pollfds for {}: {}'.format(self.device))
            self.pollfds = pfds
        return self.pollfds[0].fd
