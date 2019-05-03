import os
import logging

import peewee as pw

from mg import schema

log = logging.getLogger('db')


DB = pw.SqliteDatabase(None)


# logger = logging.getLogger('peewee')
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)


class BaseModel(pw.Model):
    class Meta:
        database = DB


class Preset(BaseModel):
    name = pw.CharField(max_length=255)
    number = pw.IntegerField(unique=True, null=True)
    data = pw.TextField(default='{}')

    data_schema = schema.PresetSchema()

    class Meta:
        order_by = ['number']

    def __str__(self):
        return '<Preset id:{}, number:{}, name:{}>'.format(
            self.id, self.number, self.name)

    @DB.atomic()
    def save(self, *args, **kwargs):
        if self.number is None:
            highest = Preset.select(pw.fn.MAX(Preset.number)).scalar() or 0
            self.number = highest + 1
        super().save(*args, **kwargs)

    @DB.atomic()
    def delete_instance(self, *args, **kwargs):
        ret = super().delete_instance(*args, **kwargs)
        ids = [p.id for p in Preset.select(Preset.id)]
        self.reorder(ids)
        return ret

    @classmethod
    @DB.atomic()
    def reorder(self, order):
        num = Preset.update(number=None).execute()
        assert len(order) == num
        for (number, pid) in enumerate(order):
            Preset.update(number=number+1).where(Preset.id == pid).execute()

    def get_data(self):
        try:
            return self.data_schema.loads(self.data).data
        except:
            log.exception('Unable to read data on preset {}'.format(self.id))
            return {}

    def set_data(self, data):
        try:
            self.data = self.data_schema.dumps(data).data
        except:
            log.exception('Unable to store data on preset {}'.format(self.id))
            self.data = '{}'

    def to_dict(self):
        data = self.get_data()
        data['id'] = self.id
        data['number'] = self.number
        data['name'] = self.name
        for voice in data.get('voices', {}).get('trompette', []):
            if not voice.get('mode'):
                voice['mode'] = 'midigurdy'
        return data


class Config(BaseModel):
    name = pw.CharField(max_length=255, primary_key=True)
    data = pw.TextField(default='{}')


class Version(BaseModel):
    name = pw.CharField(max_length=255, primary_key=True)
    version = pw.IntegerField(default=0)


def load_mapping_ranges(name):
    try:
        entry = Config.get(Config.name == name)
    except Config.DoesNotExist:
        return None
    try:
        return schema.MappingSchema().loads(entry.data).data['ranges']
    except:
        log.exception('Unable to read mapping "%s" from database', name)


def save_mapping_ranges(name, ranges):
    entry, _created = Config.get_or_create(name=name)
    try:
        entry.data = schema.MappingSchema().dumps({'ranges': ranges}).data
    except:
        log.exception('Unable to serialize mapping "%s"', name)
        raise
    try:
        entry.save()
    except:
        log.exception('Unable to write mapping "%s" to database', name)
        raise


def delete_mapping_ranges(name):
    try:
        Config.delete().where(Config.name == name).execute()
    except:
        log.exception('Unable to delete mapping "%s"', name)


def load_key_calibration():
    try:
        entry = Config.get(Config.name == 'key_calibration')
    except Config.DoesNotExist:
        return None
    try:
        return schema.KeyCalibrationSchema(many=True).loads(entry.data).data
    except:
        log.exception('Unable to read key calibration from database')


def save_key_calibration(calib):
    entry, _created = Config.get_or_create(name='key_calibration')
    try:
        entry.data = schema.KeyCalibrationSchema(many=True).dumps(calib).data
    except:
        log.exception('Unable to serialize key calibration')
        raise
    try:
        entry.save()
    except:
        log.exception('Unable to write key calibration')
        raise


def delete_key_calibration():
    try:
        Config.delete().where(Config.name == 'key_calibration').execute()
    except:
        log.exception('Unable to delete key calibration')


def load_misc_config():
    try:
        entry = Config.get(Config.name == 'misc')
    except Config.DoesNotExist:
        return None
    try:
        return schema.MiscSchema().loads(entry.data).data
    except:
        log.exception('Unable to read misc config')


def save_misc_config(config):
    entry, _created = Config.get_or_create(name='misc')
    try:
        entry.data = schema.MiscSchema().dumps(config).data
    except:
        log.exception('Unable to serialize misc config')
        raise
    try:
        entry.save()
    except:
        log.exception('Unable to write misc_config')
        raise


def load_midi_config(port_id):
    config_key = 'midi:{}'.format(port_id)[0:255]
    try:
        entry = Config.get(Config.name == config_key)
    except Config.DoesNotExist:
        return None
    try:
        return schema.MidiSchema().loads(entry.data).data
    except:
        log.exception('Unable to read midi config')


def save_midi_config(port_id, config):
    config_key = 'midi:{}'.format(port_id)[0:255]
    entry, _created = Config.get_or_create(name=config_key)
    try:
        entry.data = schema.MidiSchema().dumps(config).data
    except:
        log.exception('Unable to serialize midi config')
        raise
    try:
        entry.save()
    except:
        log.exception('Unable to write midi config')
        raise


def initialize(filepath):
    DB.init(filepath)
    DB.create_tables([Preset, Config, Version], safe=True)


def get_schema_version():
    try:
        return Version.get(Version.name == 'schema').version
    except:
        return None


def update_schema_version(version):
    Version.get_or_create(name='schema', version=version)


def migrate(filepath):
    version = get_schema_version()
    if version is None:
        try:
            DB.close()
        except:
            pass
        if os.path.isfile(filepath):
            os.unlink(filepath)
        initialize(filepath)
        update_schema_version(1)
