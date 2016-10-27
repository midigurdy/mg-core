import collections
import glob
import os
import re
import struct

from mg.conf import settings


Sound = collections.namedtuple(
    'Sound', ['soundfont', 'bank', 'program', 'name', 'type', 'base_note'])


FILENAME_PATTERN = re.compile(r'\.sf[23]$', re.I)


class SoundFont(object):
    def __init__(self, filepath=None):
        if filepath and not filepath.startswith('/'):
            filepath = os.path.join(settings.sound_dir, filepath)

        self.filepath = filepath
        if self.filepath:
            self.filename = os.path.basename(filepath)
            self.id = self.filename
            self.filesize = os.path.getsize(filepath)

        self.sounds = []
        self.name = ''
        self.copyright = ''
        self.creation_date = ''
        self.author = ''
        self.tool = ''
        self.description = ''
        self.mode = 'generic'

        if self.filepath:
            with open(self.filepath, 'rb') as f:
                self.parse_file(f)

    @classmethod
    def load_all(cls):
        sounds = []
        for path in glob.glob(os.path.join(settings.sound_dir, '*')):
            if FILENAME_PATTERN.search(path):
                sounds.append(cls(path))
        return sorted(sounds, key=lambda x: x.name + x.id)

    @classmethod
    def by_id(cls, id):
        filepath = os.path.join(settings.sound_dir, '{}'.format(id))
        try:
            return cls(filepath)
        except FileNotFoundError:
            return None

    def as_dict(self):
        result = {}
        for name in ('id', 'filename', 'filesize', 'mode',
                     'name', 'copyright', 'creation_date',
                     'author', 'tool', 'description'):
            result[name] = getattr(self, name)
        result['sounds'] = [{
            'id': '{}:{}:{}'.format(self.id, s.bank, s.program),
            'bank': s.bank,
            'program': s.program,
            'name': s.name,
            'type': s.type,
            'note': s.base_note,
        } for s in self.sounds]
        return result

    def get_sound(self, bank, progam):
        for sound in self.sounds:
            if sound.bank == bank and sound.program == progam:
                return sound

    def parse_file(self, f):
        sf2 = Sf2File(f)

        self._parse_metadata(sf2)

        for bank, program, name in sf2.presets:
            self.sounds.append(self._parse_preset(bank, program, name))

    def _parse_preset(self, bank, program, name):
        """
        The MidiGurdy expects the different types of sounds in certain banks.
            Melody Sounds: Bank 0
            Drone Sounds: Bank 1
            Trompette Sounds: Bank 2
            Key Noise Sounds: Bank 3
        """
        if self.mode == 'midigurdy':
            if bank == 0:
                type = 'melody'
            elif bank == 1:
                type = 'drone'
            elif bank == 2:
                type = 'trompette'
            elif bank == 3:
                type = 'keynoise'
            else:
                type = 'generic'

            base_note = self.base_notes.get((bank, program), -1)
        else:
            type = 'generic'
            base_note = -1

        return Sound(self, bank, program, name, type, base_note)

    def _parse_metadata(self, sf2):
        self.name = sf2.strings['font_name'] or 'Unnamed'
        self.copyright = sf2.strings['copyright']
        self.creation_date = sf2.strings['creation_date']
        self.author = sf2.strings['designers']
        self.tool = sf2.strings['tool']

        # parse product name to determine if this is a special font for the MidiGurdy
        product = sf2.strings['product'].lower()
        if 'midigurdy' in product:
            self.mode = 'midigurdy'
            self.base_notes, self.description = self._parse_comments(sf2.strings['comments'])
        else:
            self.mode = 'generic'
            self.description = sf2.strings['comments']
            self.base_notes = {}

    def _parse_comments(self, comments):
        """
        MidiGurdy SoundFonts can specify the 'natural' base notes for presets
        by special commands in the comments field:
            basenote <bank>:<prog> <note>

        They will be parsed and then removed from the comment. The remaining string
        is then used as the description.
        """
        basenote_re = re.compile(r'basenote\s+(\d+)\s*:\s*(\d+)\s+(\d+)')
        base_notes = {}
        for (bank, prog, note) in basenote_re.findall(comments):
            try:
                bank = int(bank)
                prog = int(prog)
                note = int(note)
            except (ValueError, TypeError):
                continue
            base_notes[(bank, prog)] = note
        description = basenote_re.sub('', comments).strip()
        return base_notes, description

    def __repr__(self):
        return '<SoundFont: {}>'.format(self.name)


class EndOfFile(Exception):
    pass


class Sf2File(object):
    """
    Parses a SoundFont file and extracts the presets and info
    header strings
    """

    def __init__(self, sf2file):
        self.file = sf2file
        self.list_size = 0
        self.presets = []
        self.strings = {key: '' for key in self.string_map.values()}
        try:
            self.parse_next()
        except EndOfFile:
            pass

    def parse_size(self):
        chunk_size, = struct.unpack(r'<I', self.file.read(4))
        return chunk_size

    def parse_next(self):
        data = self.file.read(4)

        if len(data) < 4:
            raise EndOfFile()

        chunk_id, = struct.unpack(r'4s', data)

        parser_method = self.parser_map.get(chunk_id)
        if parser_method:
            parser_method(self, chunk_id)
        else:
            raise RuntimeError('Invalid chunk in file: {}'.format(chunk_id))

    def parse_riff(self, chunk_id):
        self.parse_size()
        self.parse_next()

    def parse_sfbk(self, chunk_id):
        self.parse_next()
        self.parse_next()
        self.parse_next()

    def parse_list(self, chunk_id):
        self.list_size = self.parse_size()
        self.parse_next()

    def parse_array(self, chunk_id):
        end_size = self.file.tell() + self.list_size - 4
        while self.file.tell() < end_size:
            self.parse_next()

    def parse_version(self, chunk_id):
        self.parse_size()
        major, minor = struct.unpack(r'<HH', self.file.read(4))
        self.strings['version'] = '{:.2}'.format(major + minor / 100.)

    def parse_short_str(self, chunk_id):
        size = min(self.parse_size(), 256)
        name = self.string_map[chunk_id]
        self.strings[name] = from_cstr(self.file.read(size))

    def parse_long_str(self, chunk_id):
        size = min(self.parse_size(), 65536)
        name = self.string_map[chunk_id]
        self.strings[name] = from_cstr(self.file.read(size))

    def parse_phdr(self, chunk_id):
        end_pos = self.file.tell() + self.parse_size()
        while self.file.tell() < end_pos:
            data = struct.unpack(r'<20sHHHIII', self.file.read(38))
            (name, prog, bank, _, _, _, _) = data
            self.presets.append((bank, prog, from_cstr(name)))
        self.presets.pop()  # last preset is EOP marker
        self.presets.sort()

    def ignore_chunk(self, chunk_id):
        self.parse_next()

    def skip_chunk(self, chunk_id):
        self.file.seek(self.parse_size(), 1)

    parser_map = {
        b'RIFF': parse_riff,
        b'LIST': parse_list,
        b'sfbk': parse_sfbk,
        b'INFO': parse_array,
        b'ifil': parse_version,
        b'isng': parse_short_str,
        b'INAM': parse_short_str,
        b'irom': parse_short_str,
        b'iver': parse_short_str,
        b'ICRD': parse_short_str,
        b'IENG': parse_short_str,
        b'IPRD': parse_short_str,
        b'ICOP': parse_short_str,
        b'ICMT': parse_long_str,
        b'ISFT': parse_short_str,
        b'sdta': parse_array,
        b'smpl': skip_chunk,
        b'sm24': skip_chunk,
        b'pdta': ignore_chunk,
        b'phdr': parse_phdr,
    }

    string_map = {
        b'irom': 'rom_name',
        b'iver': 'rom_version',
        b'ICRD': 'creation_date',
        b'IENG': 'designers',
        b'IPRD': 'product',
        b'ICOP': 'copyright',
        b'ICMT': 'comments',
        b'ISFT': 'tool',
        b'INAM': 'font_name',
        b'isng': 'sound_engine',
    }


def from_cstr(cstr):
    if cstr is None:
        return None
    result = cstr.partition(b'\0')[0]
    return result.decode('latin1', errors='replace')
