"""A container for a Pico-8 game, and routines to load and save game files."""


__all__ = [
    'Game',
    'InvalidP8HeaderError',
    'InvalidP8SectionError'
]


import re

from .. import util
from ..lua.lua import Lua
from ..lua.lua import PICO8_LUA_CHAR_LIMIT
from ..lua.lua import PICO8_LUA_TOKEN_LIMIT
from ..gfx.gfx import Gfx
from ..gff.gff import Gff
from ..map.map import Map
from ..sfx.sfx import Sfx
from ..music.music import Music


HEADER_TITLE_STR = 'pico-8 cartridge // http://www.pico-8.com\n'
HEADER_VERSION_RE = re.compile('version (\d+)\n')
HEADER_VERSION_PAT = 'version {}\n'
SECTION_DELIM_RE = re.compile('__(\w+)__\n')
SECTION_DELIM_PAT = '__{}__\n'


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
    def __init__(self, filename=None, compressed_size=None):
        """Initializer.

        Prefer factory functions such as Game.from_p8_file().

        Args:
          filename: The filename, if any, for tool messages.
          compressed_size: The byte size of the compressed Lua data region,
            or None if the Lua region was not compressed (.p8 or v0 .p8.png).
        """
        self.filename = filename
        self.compressed_size = compressed_size
        
        self.lua = None
        self.gfx = None
        self.gff = None
        self.map = None
        self.sfx = None
        self.music = None

        self.version = None

    @classmethod
    def make_empty_game(cls, filename=None):
        """Create an empty game.

        Args:
          filename: An optional filename to use with error messages.

        Returns:
          A Game instance with valid but empty data regions.
        """
        g = cls(filename=filename)
        
        g.lua = Lua(version=5)
        g.lua.update_from_lines([])
        g.gfx = Gfx(data=b'\x00' * 8192, version=5)
        g.gff = Gff(data=b'\x00' * 256, version=5)
        g.map = Map(data=b'\x00' * 4096, version=5)
        # TODO: match Pico-8's defaults for sfx speeds
        g.sfx = Sfx(data=b'\x00' * 4352, version=5)
        g.music = Music(data=b'\0x41\0x42\0x43\0x44' * 64, version=5)
        g.version = 5

        return g
        
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
        if filename.endswith('.p8'):
            with open(filename, 'r', encoding='utf-8') as fh:
                g = Game.from_p8_file(fh, filename=filename)
        else:
            with open(filename, 'rb') as fh:
                g = Game.from_p8png_file(fh, filename=filename)
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
        new_game.version = version
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

        compressed_size = None

        if version == 0 or bytes(code[:4]) != b':c:\x00':
            # code is ASCII

            # (I assume this fails if uncompressed code completely
            # fills the code area, in which case code_length =
            # 0x8000-0x4300.)
            code_length = code.index(0)

            code = ''.join(chr(c) for c in code[:code_length]) + '\n'
                
        elif version == 1 or version == 5:
            # code is compressed
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

            code = ''.join(chr(c) for c in out) + '\n'
            compressed_size = in_i

        new_game = cls(filename=filename, compressed_size=compressed_size)
        new_game.version = version
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
        
    def to_p8_file(self, outstr, lua_writer_cls=None, lua_writer_args=None,
                   filename=None):
        """Write the game data as a .p8 file.

        Args:
          outstr: The output stream.
          lua_writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          lua_writer_args: Args to pass to the Lua writer.
          filename: The output filename, for error messages.
        """
        outstr.write(HEADER_TITLE_STR)
        
        # Even though we can get the original cart version, we
        # hard-code version 5 for output because we only know how to
        # write v5 .p8 files. There are minor changes from previous
        # versions of .p8 that don't apply to .p8.png (such as the gff
        # section).
        outstr.write(HEADER_VERSION_PAT.format(5))

        outstr.write(SECTION_DELIM_PAT.format('lua'))
        ended_in_newline = None
        for l in self.lua.to_lines(writer_cls=lua_writer_cls,
                                   writer_args=lua_writer_args):
            outstr.write(l)
            ended_in_newline = l.endswith('\n')
        if not ended_in_newline:
            outstr.write('\n')

        # Sanity-check the Lua written by the writer.
        transformed_lua = Lua.from_lines(
            self.lua.to_lines(writer_cls=lua_writer_cls),
            version=(self.version or 0))
        if transformed_lua.get_char_count() > PICO8_LUA_CHAR_LIMIT:
            if filename is not None:
                util.error('{}: '.format(filename))
            util.error('warning: character count {} exceeds the Pico-8 '
                       'limit of {}'.format(
                           transformed_lua.get_char_count(),
                           PICO8_LUA_CHAR_LIMIT))
        if transformed_lua.get_token_count() > PICO8_LUA_TOKEN_LIMIT:
            if filename is not None:
                util.error('{}: '.format(filename))
            util.error('warning: token count {} exceeds the Pico-8 '
                       'limit of {}'.format(
                           transformed_lua.get_char_count(),
                           PICO8_LUA_CHAR_LIMIT))

        outstr.write(SECTION_DELIM_PAT.format('gfx'))
        for l in self.gfx.to_lines():
            outstr.write(l)
            
        outstr.write(SECTION_DELIM_PAT.format('gff'))
        for l in self.gff.to_lines():
            outstr.write(l)
            
        outstr.write(SECTION_DELIM_PAT.format('map'))
        for l in self.map.to_lines():
            outstr.write(l)
            
        outstr.write(SECTION_DELIM_PAT.format('sfx'))
        for l in self.sfx.to_lines():
            outstr.write(l)
            
        outstr.write(SECTION_DELIM_PAT.format('music'))
        for l in self.music.to_lines():
            outstr.write(l)

        outstr.write('\n')
