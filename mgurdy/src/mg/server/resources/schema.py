from marshmallow import Schema, fields, validate

midi_range = validate.Range(min=0, max=127)


class KeyCalibrationSchema(Schema):
    pressure = fields.Int(validate=validate.Range(min=0, max=3000))
    velocity = fields.Int(validate=validate.Range(min=-100, max=100))
