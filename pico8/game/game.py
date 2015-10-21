"""A container for a Pico-8 game, and routines to load and save game files."""


__all__ = [
    'Game',
    'InvalidP8HeaderError',
    'InvalidP8SectionError'
]


import re

from .. import util
from ..lua.lua import Lua
from ..gfx.gfx import Gfx
from ..gff.gff import Gff
from ..map.map import Map
from ..sfx.sfx import Sfx
from ..music.music import Music


HEADER_TITLE_STR = 'pico-8 cartridge // http://www.pico-8.com\n'
HEADER_VERSION_RE = re.compile('version (\d+)\n')
SECTION_DELIM_RE = re.compile('__(\w+)__\n')


class InvalidP8HeaderError(util.InvalidP8DataError):
    """Exception for invalid .p8 file header."""
    def __str__(self):
        return 'Invalid .p8: missing or corrupt header'

    
class InvalidP8SectionError(util.InvalidP8DataError):
    """Exception for invalid .p8 file section delimiter."""
    def __init__(self, bad_delim):
        self.bad_delim = bad_delim
    def __str__(self):
        return 'Invalid .p8: bad section delimiter {}'.format(
            repr(self.bad_delim))


class Game():
    """A Pico-8 game."""
    def __init__(self, filename=None):
        """Initializer.

        Prefer factory functions such as Game.from_p8_file().

        Args:
          filename: The filename, if any, for tool messages.
        """
        self.filename = filename
        self.lua = None
        self.gfx = None
        self.gff = None
        self.map = None
        self.sfx = None
        self.music = None

    @classmethod
    def from_filename(cls, filename):
        """Loads a game from a named file.

        Args:
          filename: The name of the file. Must end in either ".p8" or ".p8.png".

        Returns:
          A Game containing the game data.

        Raises:
          lexer.LexerError
          parser.ParserError
          InvalidP8HeaderError
        """
        assert filename.endswith('.p8.png') or filename.endswith('.p8')
        if fname.endswith('.p8'):
            with open(fname, 'r') as fh:
                g = game.Game.from_p8_file(fh, filename=filename)
        else:
            with open(fname, 'rb') as fh:
                g = game.Game.from_p8png_file(fh, filename=filename)
        return g


    @classmethod
    def from_p8_file(cls, instr, filename=None):
        """Loads a game from a .p8 file.
    
        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.
    
        Returns:
          A Game containing the game data.
    
        Raises:
          InvalidP8HeaderError
        """
        header_title_str = instr.readline()
        if header_title_str != HEADER_TITLE_STR:
            raise InvalidP8HeaderError()
        header_version_str = instr.readline()
        version_m = HEADER_VERSION_RE.match(header_version_str)
        if version_m is None:
            raise InvalidP8HeaderError()
        version = int(version_m.group(1))
    
        section = None
        section_lines = {}
        while True:
            line = instr.readline()
            if not line:
                break
            section_delim_m = SECTION_DELIM_RE.match(line)
            if section_delim_m:
                section = section_delim_m.group(1)
                section_lines[section] = []
            elif section:
                section_lines[section].append(line)
    
        new_game = cls(filename=filename)
        for section in section_lines:
            if section == 'lua':
                new_game.lua = Lua.from_lines(
                    section_lines[section], version=version)
            elif section == 'gfx':
                new_game.gfx = Gfx.from_lines(
                    section_lines[section], version=version)
            elif section == 'gff':
                new_game.gff = Gff.from_lines(
                    section_lines[section], version=version)
            elif section == 'map':
                new_game.map = Map.from_lines(
                    section_lines[section], version=version)
            elif section == 'sfx':
                new_game.sfx = Sfx.from_lines(
                    section_lines[section], version=version)
            elif section == 'music':
                new_game.music = Music.from_lines(
                    section_lines[section], version=version)
            else:
                raise InvalidP8SectionError(section)
    
        return new_game

    @classmethod
    def from_p8png_file(cls, instr, filename=None):
        """Loads a game from a .p8.png file.
    
        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.
    
        Returns:
          A Game containing the game data.
        """
        # To install: python3 -m pip install pypng
        import png
        r = png.Reader(file=instr)

        (width, height, data, attrs) = r.read()
        picodata = [0] * width * height

        row_i = 0
        for row in data:
            for col_i in range(width):
                picodata[row_i * width + col_i] |= (
                    (row[col_i * attrs['planes'] + 2] & 3) << (0 * 2))
                picodata[row_i * width + col_i] |= (
                    (row[col_i * attrs['planes'] + 1] & 3) << (1 * 2))
                picodata[row_i * width + col_i] |= (
                    (row[col_i * attrs['planes'] + 0] & 3) << (2 * 2))
                picodata[row_i * width + col_i] |= (
                    (row[col_i * attrs['planes'] + 3] & 3) << (3 * 2))
            row_i += 1

        gfx = picodata[0x0:0x2000]
        p8map = picodata[0x2000:0x3000]
        gfx_props = picodata[0x3000:0x3100]
        song = picodata[0x3100:0x3200]
        sfx = picodata[0x3200:0x4300]
        code = picodata[0x4300:0x8000]
        version = picodata[0x8000]

        if version == 0:
            # code is ASCII

            # (Technically this fails if v0 code completely fills the code area,
            # in which case code_length = 0x8000-0x4300.)
            code_length = code.index(0)

            code = ''.join(chr(c) for c in code[:code_length])
                
        if version == 1 or version == 5:
            # code is compressed
            assert bytes(code[:4]) == b':c:\x00'
            code_length = (code[4] << 8) | code[5]
            assert bytes(code[6:8]) == b'\x00\x00'

            chars = list(b'#\n 0123456789abcdefghijklmnopqrstuvwxyz!#%(){}[]<>+=/*:;.,~_')
            out = [0] * code_length
            in_i = 8
            out_i = 0
            while out_i < code_length and in_i < len(code):
                if code[in_i] == 0x00:
                    in_i += 1
                    out[out_i] = code[in_i]
                    out_i += 1
                elif code[in_i] <= 0x3b:
                    out[out_i] = chars[code[in_i]]
                    out_i += 1
                else:
                    in_i += 1
                    offset = (code[in_i - 1] - 0x3c) * 16 + (code[in_i] & 0xf)
                    length = (code[in_i] >> 4) + 2
                    out[out_i:out_i+length] = out[out_i-offset:out_i-offset+length]
                    out_i += length
                in_i += 1

            code = ''.join(chr(c) for c in out)

        new_game = cls(filename=filename)
        new_game.lua = Lua.from_lines(
            [code], version=version)
        new_game.gfx = Gfx.from_bytes(
            gfx, version=version)
        new_game.gff = Gff.from_bytes(
            gfx_props, version=version)
        new_game.map = Map.from_bytes(
            p8map, version=version)
        new_game.sfx = Sfx.from_bytes(
            sfx, version=version)
        new_game.music = Music.from_bytes(
            song, version=version)
    
        return new_game
        
