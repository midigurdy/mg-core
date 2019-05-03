from ._mglib import lib, ffi


STRINGS = {
    'melody1': lib.MG_MELODY1,
    'melody2': lib.MG_MELODY2,
    'melody3': lib.MG_MELODY3,
    'trompette1': lib.MG_TROMPETTE1,
    'trompette2': lib.MG_TROMPETTE2,
    'trompette3': lib.MG_TROMPETTE3,
    'drone1': lib.MG_DRONE1,
    'drone2': lib.MG_DRONE2,
    'drone3': lib.MG_DRONE3,
    'keynoise1': lib.MG_KEYNOISE,
}

PARAMS = {
    'mute': lib.MG_PARAM_MUTE,
    'volume': lib.MG_PARAM_VOLUME,
    'polyphonic': lib.MG_PARAM_POLYPHONIC,
    'chien_threshold': lib.MG_PARAM_THRESHOLD,
    'chien_attack': lib.MG_PARAM_ATTACK,
    'capo': lib.MG_PARAM_EMPTY_KEY,
    'panning': lib.MG_PARAM_PANNING,
    'note_on': lib.MG_PARAM_NOTE_ENABLE,
    'note_off': lib.MG_PARAM_NOTE_ENABLE,
    'all_notes_off': lib.MG_PARAM_NOTE_CLEAR,
    'base_note': lib.MG_PARAM_BASE_NOTE,
    'reset': lib.MG_PARAM_RESET,
    'mode': lib.MG_PARAM_MODE,
    'bank': lib.MG_PARAM_BANK,
    'program': lib.MG_PARAM_PROGRAM,
}

MAPPINGS = {
    'pressure_to_poly': {
        'idx': lib.MG_MAP_PRESSURE_TO_POLY,
        'name': 'Key Pressure to Polyphonic Aftertouch',
        'src': {
            'name': 'Key Pressure',
            'min': 0,
            'max': 3000,
        },
        'dst': {
            'name': 'Polyphonic Aftertouch',
            'min': 0,
            'max': 127,
        },
    },
    'pressure_to_pitch': {
        'idx': lib.MG_MAP_PRESSURE_TO_PITCH,
        'name': 'Key Pressure to Pitch Bend',
        'src': {
            'name': 'Key Pressure',
            'min': 0,
            'max': 3000,
        },
        'dst': {
            'name': 'Pitch Bend',
            'min': -0x2000,
            'max': 0x2000,
        },
    },
    'speed_to_melody_volume': {
        'idx': lib.MG_MAP_SPEED_TO_MELODY_VOLUME,
        'name': 'Wheel Speed to Melody Volume',
        'src': {
            'name': 'Wheel Speed',
            'min': 0,
            'max': 5000,
        },
        'dst': {
            'name': 'Melody Volume',
            'min': 0,
            'max': 127,
        },
    },
    'speed_to_drone_volume': {
        'idx': lib.MG_MAP_SPEED_TO_DRONE_VOLUME,
        'name': 'Wheel Speed to Drone Volume',
        'src': {
            'name': 'Wheel Speed',
            'min': 0,
            'max': 5000,
        },
        'dst': {
            'name': 'Drone Volume',
            'min': 0,
            'max': 127,
        },
    },
    'speed_to_trompette_volume': {
        'idx': lib.MG_MAP_SPEED_TO_TROMPETTE_VOLUME,
        'name': 'Wheel Speed to Trompette Volume',
        'src': {
            'name': 'Wheel Speed',
            'min': 0,
            'max': 5000,
        },
        'dst': {
            'name': 'Trompette Volume',
            'min': 0,
            'max': 127,
        },
    },
    'speed_to_chien': {
        'idx': lib.MG_MAP_SPEED_TO_CHIEN,
        'name': 'Coup Speed to Chien Volume',
        'src': {
            'name': 'Coup Speed',
            'min': 0,
            'max': 4000,
        },
        'dst': {
            'name': 'Chien Volume',
            'min': 0,
            'max': 127,
        },
    },
    'chien_threshold_to_range': {
        'idx': lib.MG_MAP_CHIEN_THRESHOLD_TO_RANGE,
        'name': 'Chien Sensitivity to Chien Hardness',
        'src': {
            'name': 'Chien Sensitivity %',
            'min': 0,
            'max': 100,
        },
        'dst': {
            'name': 'Chien Hardness',
            'min': -500,
            'max': 500,
        },
    },
    'speed_to_percussion': {
        'idx': lib.MG_MAP_SPEED_TO_PERCUSSION,
        'name': 'Wheel Speed to Percussion Volume',
        'src': {
            'name': 'Wheel Speed',
            'min': 0,
            'max': 1000,
        },
        'dst': {
            'name': 'Percussion Volume',
            'min': 0,
            'max': 127,
        },
    },
    'keyvel_to_notevel': {
        'idx': lib.MG_MAP_KEYVEL_TO_NOTEVEL,
        'name': 'Key Hit Velocity to Keyboard Volume',
        'src': {
            'name': 'Key Velocity',
            'min': 0,
            'max': 3000,
        },
        'dst': {
            'name': 'Keyboard Volume',
            'min': 0,
            'max': 127,
        },
    },
    'keyvel_to_tangent': {
        'idx': lib.MG_MAP_KEYVEL_TO_TANGENT,
        'name': 'Key Hit Velocity to Tangent Hit Volume',
        'src': {
            'name': 'Key Velocity',
            'min': 0,
            'max': 3000,
        },
        'dst': {
            'name': 'Tangent Hit Volume',
            'min': 0,
            'max': 63,
        },
    },
    'keyvel_to_keynoise': {
        'idx': lib.MG_MAP_KEYVEL_TO_KEYNOISE,
        'name': 'Key Hit Velocity to Keynoise Volume',
        'src': {
            'name': 'Key Velocity',
            'min': 0,
            'max': 3000,
        },
        'dst': {
            'name': 'Keynoise Volume',
            'min': 0,
            'max': 127,
        },
    },
}


class MGCore:
    def __init__(self):
        self.synth = None
        self.started = False
        self.outputs = {}

        if lib.mg_initialize():
            raise RuntimeError('Unable to initialize mgcore')

    def start(self, synth):
        self.synth = synth
        if lib.mg_start(self.synth.synth if self.synth else ffi.NULL):
            raise RuntimeError('Unable to start mgcore')
        self.started = True

    def stop(self):
        if self.started:
            lib.mg_stop()
            self.started = False

    def mute_string(self, string, muted):
        cfg = (string, 'mute', 1 if muted else 0)
        self.set_string_params([cfg])

    def mute_all(self, muted):
        cfg = [(s, 'mute', 1 if muted else 0) for s in STRINGS]
        self.set_string_params([cfg])

    def halt_midi_output(self):
        if lib.mg_halt_midi_output(1):
            raise RuntimeError('Unable to halt midi output')

    def resume_midi_output(self):
        if lib.mg_halt_midi_output(0):
            raise RuntimeError('Unable to resume midi output')

    def get_wheel_gain(self):
        return lib.mg_get_wheel_gain()

    def set_pitchbend_range(self, val):
        val = max(0, min(200, val))
        factor = float(val / 200)
        lib.mg_set_pitchbend_factor(factor)

    def set_key_on_debounce(self, val):
        lib.mg_set_key_on_debounce(val)

    def set_key_off_debounce(self, val):
        lib.mg_set_key_off_debounce(val)

    def set_base_note_delay(self, val):
        lib.mg_set_base_note_delay(val)

    def set_string_params(self, configs):
        cfgs = []

        for (string, param, val) in configs:
            cfgs.append({
                'string': STRINGS[string],
                'param': PARAMS[param],
                'val': val,
            })

        # add list end sentinel
        cfgs.append({'param': lib.MG_PARAM_END})

        # print('\nsetting string params------')
        # for (string, param, val) in configs:
        #    print('  ', string, param, val)

        params = ffi.new("struct mg_string_config[]", cfgs)
        lib.mg_set_string(params)

    def get_mapping_configs(self):
        return MAPPINGS

    def get_mapping_ranges(self, name):
        mapcfg = MAPPINGS[name]
        mapping = ffi.new('struct mg_map *map')
        if lib.mg_get_mapping(mapping, mapcfg['idx']) != 0:
            raise RuntimeError('Unable to get mapping ranges from core!')
        ranges = []
        for i in range(mapping.count):
            ranges.append({'src': mapping.ranges[i][0],
                           'dst': mapping.ranges[i][1]})
        return ranges

    def set_mapping_ranges(self, name, ranges):
        mapcfg = MAPPINGS[name]
        mapping = ffi.new('struct mg_map *map')
        mapping.count = len(ranges)
        for i, entry in enumerate(ranges):
            mapping.ranges[i][0] = entry['src']
            mapping.ranges[i][1] = entry['dst']
        if lib.mg_set_mapping(mapping, mapcfg['idx']) != 0:
            raise RuntimeError('Unable to set mapping ranges for %s', name)

    def reset_mapping_ranges(self, name):
        mapcfg = MAPPINGS[name]
        if lib.mg_reset_mapping_ranges(mapcfg['idx']) != 0:
            raise RuntimeError('Unable to reset mapping ranges for %s', name)

    def get_key_calibration(self):
        data = []
        pressure = ffi.new('float *')
        velocity = ffi.new('float *')
        for i in range(24):
            if lib.mg_calibrate_get_key(i, pressure, velocity) != 0:
                raise RuntimeError('Unable to get key calib data!')
            data.append({'pressure': float(pressure), 'velocity': float(velocity)})
        return data

    def set_key_calibration(self, data):
        for i, data in enumerate(data):
            if lib.mg_calibrate_set_key(i,
                                        float(data['pressure']),
                                        float(data['velocity'])) != 0:
                raise RuntimeError('Unable to set key calib data!')

    def add_midi_output(self, device):
        if device in self.outputs:
            return self.outputs[device]
        output_id = lib.mg_add_midi_output(device.encode())
        if output_id < 0:
            raise RuntimeError('Unable to add MIDI output')
        self.outputs[device] = output_id
        return output_id

    def enable_midi_output(self, device, enabled=True):
        if device not in self.outputs:
            raise RuntimeError('MIDI output %s not found' % device)
        if lib.mg_enable_midi_output(self.outputs[device], 1 if enabled else 0):
            raise RuntimeError('Unable to set MIDI output enable state')

    def config_midi_output(self, device, melody_channel, drone_channel, trompette_channel, program_change, speed):
        if device not in self.outputs:
            raise RuntimeError('MIDI output %s not found' % device)
        if lib.mg_config_midi_output(self.outputs[device],
                                     int(melody_channel),
                                     int(drone_channel),
                                     int(trompette_channel),
                                     int(program_change),
                                     int(speed)):
            raise RuntimeError('Unable to configure MIDI output')

    def remove_midi_output(self, device):
        if device not in self.outputs:
            raise RuntimeError('MIDI output %s not found' % device)
        if lib.mg_remove_midi_output(self.outputs[device]):
            raise RuntimeError('Unable to remove MIDI output')
        del self.outputs[device]

    def __del__(self):
        self.stop()


class MGImage:
    def __init__(self, width, height, mmap_filename=None, filename=None):
        self.img = lib.mg_image_create(width, height, filename.encode() if filename else ffi.NULL)
        if mmap_filename:
            ret = lib.mg_image_mmap_file(self.img, mmap_filename.encode())
            if ret != 0:
                raise RuntimeError('Unable to mmap image to %s' % mmap_filename)

    def clear(self, x1=-1, y1=-1, x2=-1, y2=-1):
        lib.mg_image_clear(self.img, x1, y1, x2, y2)

    def point(self, x, y, color):
        lib.mg_image_point(self.img, x, y, color)

    def line(self, x0, y0, x1, y1, color):
        lib.mg_image_line(self.img, x0, y0, x1, y1, color)

    def rect(self, x1, y1, x2, y2, color, fill):
        lib.mg_image_rect(self.img, x1, y1, x2, y2, color, fill)

    def write(self, filename):
        lib.mg_image_write(self.img, filename.encode())

    def puts(self, x, y, text, font, color, spacing, align, anchor, max_width=0, x_offset=0):
        if align == 'center':
            align_id = 1
        elif align == 'right':
            align_id = 2
        else:
            align_id = 0

        if anchor == 'center':
            anchor_id = 1
        elif anchor == 'right':
            anchor_id = 2
        else:
            anchor_id = 0

        lib.mg_image_puts(self.img, font, text.encode('latin-1'),
                          x, y, color, spacing, align_id, anchor_id, max_width, x_offset)

    def scrolltext(self, x, y, width, text, font, color, initial_delay=0, shift_delay=0, end_delay=0):
        lib.mg_image_scrolltext(self.img, font, text.encode('latin-1'),
                                x, y, width, color, initial_delay, shift_delay, end_delay)

    def get_image_data(self):
        """
        This is not very fast, only used for testing purposes (Tk Display)
        """
        data = bytearray()
        bit = 0
        byte = 0
        for pixel in list(bytes(ffi.buffer(self.img.data, self.img.size))):
            byte |= pixel << bit
            if bit == 7:
                data.append(byte)
                byte = 0
                bit = 0
            else:
                bit += 1
        return bytes(data)

    def load_font(self, filename):
        return lib.mg_image_load_font(self.img, filename.encode())

    def __del__(self):
        try:
            lib.mg_image_destroy(self.img)
        except:
            pass
