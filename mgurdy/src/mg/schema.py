from marshmallow import Schema, fields, validate, ValidationError


midi_range = validate.Range(min=0, max=127)
bank_range = validate.Range(min=0, max=128)
percent_range = validate.Range(min=0, max=100)
debounce_range = validate.Range(min=0, max=50)


class VoiceSchema(Schema):
    soundfont = fields.Str(default=None, allow_none=True)
    bank = fields.Int(default=0, validate=bank_range)
    program = fields.Int(default=0, validate=midi_range)
    volume = fields.Int(default=127, validate=midi_range)
    panning = fields.Int(default=64, validate=midi_range)
    muted = fields.Boolean(default=True)
    note = fields.Int(default=60, validate=validate.Range(min=-1, max=127))
    finetune = fields.Int(default=0, validate=validate.Range(min=-100, max=100))
    chien_threshold = fields.Int(default=50, validate=percent_range)


class MelodySchema(VoiceSchema):
    capo = fields.Int(default=0, validate=validate.Range(min=0, max=23))
    polyphonic = fields.Boolean(default=False)
    mode = fields.Str(default='midigurdy')


class DroneSchema(VoiceSchema):
    pass


class TrompetteSchema(VoiceSchema):
    mode = fields.Str(default='midigurdy')


class KeynoiseSchema(VoiceSchema):
    soundfont = fields.Str(default=None, allow_none=True)
    bank = fields.Int(default=0, validate=bank_range)
    program = fields.Int(default=0, validate=midi_range)
    volume = fields.Int(default=127, validate=midi_range)
    panning = fields.Int(default=64, validate=midi_range)


class ReverbSchema(VoiceSchema):
    volume = fields.Int(default=127, validate=midi_range)
    panning = fields.Int(default=64, validate=midi_range)


class VoicesSchema(Schema):
    melody = fields.Nested(MelodySchema, many=True, validate=validate.Length(max=3))
    drone = fields.Nested(DroneSchema, many=True, validate=validate.Length(max=3))
    trompette = fields.Nested(TrompetteSchema, many=True, validate=validate.Length(max=3))


class MainSchema(Schema):
    volume = fields.Int(default=120, validate=midi_range)
    gain = fields.Int(default=50, validate=midi_range)
    pitchbend_range = fields.Int(default=100, validate=validate.Range(min=0, max=200))


class TuningSchema(Schema):
    coarse = fields.Int(default=0, validate=validate.Range(min=-63, max=64))
    fine = fields.Int(default=0, validate=validate.Range(min=-100, max=100))


class ChienSchema(Schema):
    threshold = fields.Int(default=50, validate=percent_range)


class PresetSchema(Schema):
    name = fields.Str()  # only for import/export
    main = fields.Nested(MainSchema)
    tuning = fields.Nested(TuningSchema)
    chien = fields.Nested(ChienSchema)
    voices = fields.Nested(VoicesSchema)
    reverb = fields.Nested(ReverbSchema)
    keynoise = fields.Nested(KeynoiseSchema)


class UISchema(Schema):
    brightness = fields.Int(default=60, validate=percent_range)
    timeout = fields.Int(default=10, validate=validate.Range(min=0, max=120))


class MappingRangeSchema(Schema):
    src = fields.Int(required=True)
    dst = fields.Int(required=True)


def validate_ranges(ranges):
    if not ranges or len(ranges) < 1:
        raise ValidationError('At least one range required!')
    if len(ranges) > 20:
        raise ValidationError('Maximum of 20 ranges exceeded')
    src = -1
    for row in ranges:
        if row['src'] <= src:
            raise ValidationError('Range source values must be increasing monotonically')
        src = row['src']


class MappingSchema(Schema):
    name = fields.Str()  # only for import/export
    ranges = fields.Nested(MappingRangeSchema, many=True, validate=validate_ranges)


class KeyCalibrationSchema(Schema):
    pressure = fields.Int(required=True, validate=validate.Range(min=0, max=3000))
    velocity = fields.Int(required=True, validate=validate.Range(min=-100, max=100))


class MiscUISchema(Schema):
    timeout = fields.Int(default=10, validate=validate.Range(min=0, max=1000))
    brightness = fields.Int(default=80, validate=percent_range)
    chien_sens_reverse = fields.Boolean(default=False)
    multi_chien_threshold = fields.Boolean(default=False)
    mod1_key_mode = fields.Str(default='preset_prev')
    mod2_key_mode = fields.Str(default='preset_next')
    wrap_groups = fields.Boolean(default=True)
    wrap_presets = fields.Boolean(default=True)
    string_group_by_type = fields.Boolean(default=False)


class MiscFeaturesSchema(Schema):
    poly_base_note = fields.Boolean(default=True)
    poly_pitch_bend = fields.Boolean(default=True)
    string_count = fields.Int(default=1, validate=validate.Range(min=1, max=3))


class MiscKeyboardSchema(Schema):
    key_on_debounce = fields.Int(default=2, validate=debounce_range)
    key_off_debounce = fields.Int(default=10, validate=debounce_range)
    base_note_delay = fields.Int(default=20, validate=debounce_range)


class MiscSchema(Schema):
    ui = fields.Nested(MiscUISchema)
    features = fields.Nested(MiscFeaturesSchema)
    keyboard = fields.Nested(MiscKeyboardSchema)
    instrument_mode = fields.Str(default='simple_three')


class MidiSchema(Schema):
    input_enabled = fields.Boolean(default=False)
    input_auto = fields.Boolean(default=False)
    output_enabled = fields.Boolean(default=False)
    output_auto = fields.Boolean(default=False)
    melody_channel = fields.Int(default=0)
    trompette_channel = fields.Int(default=1)
    drone_channel = fields.Int(default=2)
    program_change = fields.Boolean(default=False)
    speed = fields.Int(default=0)


class ExportSchema(Schema):
    mappings = fields.Nested(MappingSchema, many=True)
    presets = fields.Nested(PresetSchema, many=True)
    calibration = fields.Nested(KeyCalibrationSchema, many=True)
    settings = fields.Nested(MiscSchema)
