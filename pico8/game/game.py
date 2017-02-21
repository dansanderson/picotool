"""A container for a Pico-8 game, and routines to load and save game files."""

__all__ = [
    'DEFAULT_VERSION',
    'Game',
    'InvalidP8HeaderError',
    'InvalidP8SectionError'
]

import os
import re
import tempfile
from .. import util
from ..lua.lua import Lua
from ..lua.lua import PICO8_LUA_CHAR_LIMIT
from ..lua.lua import PICO8_LUA_TOKEN_LIMIT
from ..gfx.gfx import Gfx
from ..gff.gff import Gff
from ..map.map import Map
from ..sfx.sfx import Sfx
from ..music.music import Music

from ..lua.lua import LuaMinifyTokenWriter

HEADER_TITLE_STR = 'pico-8 cartridge // http://www.pico-8.com\n'
HEADER_VERSION_RE = re.compile('version (\d+)\n')
HEADER_VERSION_PAT = 'version {}\n'
SECTION_DELIM_RE = re.compile('__(\w+)__\n')
SECTION_DELIM_PAT = '__{}__\n'

DEFAULT_VERSION = 8
EMPTY_LABEL_FNAME = os.path.join(os.path.dirname(__file__), 'empty_018.p8.png')
COMPRESSED_LUA_CHAR_TABLE = list(b'#\n 0123456789abcdefghijklmnopqrstuvwxyz!#%(){}[]<>+=/*:;.,~_')

# Pico-8 adds this automatically to compressed code and removes it
# automatically from decompressed code to maintain compatibility with Pico-8
# 0.1.7.
PICO8_FUTURE_CODE2 = ('if(_update60)_update=function()'
                      '_update60()_update_buttons()_update60()end')


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


class InvalidP8PNGError(util.InvalidP8DataError):
    """Exception for PNG parsing errors."""
    pass


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
        self.label = None

        self.version = None

        self.title = None
        self.byline = None

    @classmethod
    def make_empty_game(cls, filename=None, version=DEFAULT_VERSION):
        """Create an empty game.

        Args:
          filename: An optional filename to use with error messages.
          version: The version ID of the empty game.

        Returns:
          A Game instance with valid but empty data regions.
        """
        g = cls(filename=filename)

        g.lua = Lua(version=version)
        g.lua.update_from_lines([])
        g.gfx = Gfx.empty(version=version)
        g.gff = Gff.empty(version=version)
        g.map = Map.empty(version=version, gfx=g.gfx)
        g.sfx = Sfx.empty(version=version)
        g.music = Music.empty(version=version)
        g.label = Gfx.empty(version=version)
        g.version = version

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
            with open(filename, 'r', encoding='iso-8859-1', errors='backslashreplace') as fh:
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

        # Grab the title and byline.
        title = None
        byline = None
        if len(section_lines['lua']) > 1:
            title = section_lines['lua'][0]
            byline = section_lines['lua'][1]
            if title[:2] == '--':
                title = title[2:]
                if byline[:2] == '--':
                    byline = byline[2:]
                else:
                    byline = None
            else:
                title = None
                byline = None

        #######################################
        # if ???:                             #
        # Need to make this section optional. #
        #######################################
        # Look for CONSTANT tags and process them.
        # That is, replace all constant references with their value
        # and remove the constant declarations to reclaim their tokens.
        # Assumptions:
        #   One constant assignment per line like so:
        #       --[[const]] foo = 1
        #   No other code on line. Line will be commented out like so:
        #       --[[const]]-- foo = 1
        #   Later comment okay:
        #       --[[const]] foo = 1   -- this is foo
        #   Keep the right side simple. e.g. Simplified literals.
        #     This will be a straight text replace in the code.
        #     Thus, anything complex will add tokens rather than save.
        #   No other lines should contain "--[[const]]" for any reason.
        #   Everything is case sensitive.
        CONSTANT_TAG = '--[[const]]'
        game_constants = {}
        for l in section_lines['lua']:
            tag_start = l.find(CONSTANT_TAG)
            if tag_start > -1:
                tag_end = tag_start + len(CONSTANT_TAG)
                op = l.find('=', tag_end + 1)
                if op > -1:
                    comment_start = l.find('--', op + 2)
                    ckey = l[tag_end:op].strip()
                    cval = l[op + 1:comment_start if comment_start > -1 else len(l)].strip()
                    if ckey:
                        game_constants.update({ckey: cval})
                        #print(ckey + ': ' + cval)
        # Must loop twice because it is possible to declare a global
        # in a function below where it is used.
        #for l in section_lines['lua']:
        for i in range(len(section_lines['lua'])):
            l = section_lines['lua'][i]
            # Don't replace the constant declaration itself...
            if l.find(CONSTANT_TAG) > -1:
                # comment it out...
                l = l.replace(CONSTANT_TAG, CONSTANT_TAG + '--')
            else:
                # and replace all other references to it with its value.
                for c in game_constants.items():
                    l = re.sub(r'\b' + c[0] + r'\b', c[1], l)
            # This is where I needed the index iterator.
            section_lines['lua'][i] = l

        new_game = cls.make_empty_game(filename=filename)
        # Discard empty label until one is found in the file.
        new_game.label = None
        new_game.version = version
        new_game.title = title
        new_game.byline = byline
        for section in section_lines:
            if section == 'lua':
                new_game.lua = Lua.from_lines(
                    section_lines[section], version=version)
            elif section == 'gfx':
                new_game.gfx = Gfx.from_lines(
                    section_lines[section], version=version)
                my_map = getattr(new_game, 'map')
                if my_map is not None:
                    my_map._gfx = new_game.gfx
            elif section == 'gff':
                new_game.gff = Gff.from_lines(
                    section_lines[section], version=version)
            elif section == 'map':
                my_gfx = getattr(new_game, 'gfx')
                new_game.map = Map.from_lines(
                    section_lines[section], version=version, gfx=my_gfx)
            elif section == 'sfx':
                new_game.sfx = Sfx.from_lines(
                    section_lines[section], version=version)
            elif section == 'music':
                new_game.music = Music.from_lines(
                    section_lines[section], version=version)
            elif section == 'label':
                new_game.label = Gfx.from_lines(
                    section_lines[section], version=version)
            else:
                raise InvalidP8SectionError(section)

        return new_game

    @classmethod
    def get_picodata_from_pngdata(cls, width, height, pngdata, attrs):
        """Extracts Pico-8 bytes from a .p8.png's PNG data.

        The arguments are expected in the format returned by png.Reader's
        read() method.

        Args:
          width: The PNG width.
          height: The PNG height.
          pngdata: The PNG data region, an iterable of 'height' rows, where
            each row is an indexable 'width' * 'attrs['planes']' long.
          attrs: The PNG attrs.

        Returns:
          The Pico-8 data, a list of width * height (0x8000) byte-size numbers.
        """
        picodata = [0] * width * height

        row_i = 0
        for row in pngdata:
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

        return picodata

    @classmethod
    def get_pngdata_from_picodata(cls, picodata, pngdata, attrs):
        """Encodes Pico-8 bytes into a given PNG's image data.

        Args:
          picodata: The Pico-8 data, a bytearray of 0x8000 bytes.
          pngdata: The PNG image data of the original cart image,
            as an iterable of rows as returned by pypng.
          attrs: The attrs of the original PNG image, as returned by pypng.

        Returns:
          New PNG image data, as an iterable of rows, suitable for writing
          by pypng.
        """
        new_rows = []
        planes = attrs['planes']
        for row_i, row in enumerate(pngdata):
            width = int(len(row) / planes)
            new_row = bytearray(width * planes)
            for col_i in range(width):
                if (row_i * width + col_i) < len(picodata):
                    picobyte = picodata[row_i * width + col_i]
                    new_row[col_i * planes + 2] = (
                        (row[col_i * planes + 2] & ~3) |
                        (picobyte & 3))
                    new_row[col_i * planes + 1] = (
                        (row[col_i * planes + 1] & ~3) |
                        ((picobyte >> 2) & 3))
                    new_row[col_i * planes + 0] = (
                        (row[col_i * planes + 0] & ~3) |
                        ((picobyte >> 4) & 3))
                    new_row[col_i * planes + 3] = (
                        (row[col_i * planes + 3] & ~3) |
                        ((picobyte >> 6) & 3))
                else:
                    for n in range(4):
                        new_row[col_i * planes + n] = (
                            row[col_i * planes + n])
            new_rows.append(new_row)

        return new_rows

    # TODO: "BROKEN" because I'm investigating why this doesn't match the
    # Pico-8 algorithm and produces too-large (but compatible) results.
    @classmethod
    def compress_code_BROKEN(cls, code):
        """Compress code.

        This returns the compressed code even if the output is larger than the
        input. The caller should compare the sizes and do the appropriate thing.

        Args:
          code: The code text (str), non-empty.

        Returns:
          The compressed code data (bytearray).
        """
        result = bytearray()

        # Constants from Pico-8, courtesy zep
        PICO8_BLOCK_LEN_MIN = 3
        PICO8_BLOCK_LEN_MAX = 17
        PICO8_CODE_ALLOC_SIZE = 0x10000 + 1

        # Implement Pico-8 0.1.7 forwards compatibility feature.
        # This injected code is removed by Pico-8 if it exists.
        if (len(code) + len(PICO8_FUTURE_CODE2) + 1) < PICO8_CODE_ALLOC_SIZE:
            if code[-1] != ' ' and code[-1] != '\n':
                code += '\n'
            code += PICO8_FUTURE_CODE2

        # maps string segments to (start_i, end_i) indexes in the original
        # string, or None if is a single-char entry
        lzd = {}
        for c in range(256):
            lzd[chr(c)] = None

        i = 0
        while i < len(code):
            seglen = 1
            while i + seglen <= len(code) and code[i:i + seglen] in lzd:
                seglen += 1
            seglen -= 1

            if seglen < PICO8_BLOCK_LEN_MIN:
                # emit one char
                seglen = 1
                try:
                    char_i = COMPRESSED_LUA_CHAR_TABLE.index(ord(code[i]))
                except ValueError:
                    char_i = 0
                if char_i >= 1:
                    result.append(char_i)
                else:
                    result.append(0)
                    result.append(ord(code[i]))
            else:
                # emit lzd entry
                start_i, end_i = lzd[code[i:i + seglen]]
                offset = i - start_i
                length = end_i - start_i
                result.append((offset >> 4) + 0x3c)
                result.append(((length - 2) << 4) | (offset & 0xf))

            # extend lzd
            if ((i + seglen + 1 <= len(code)) and
                (i + seglen + 1 <= PICO8_BLOCK_LEN_MAX)):
                lzd[code[i:i + seglen + 1]] = (i, i + seglen + 1)

            i += seglen

        return result

    # TODO: Compare this with compress_code_BROKEN and fix the latter.
    @classmethod
    def _find_repeatable_block(cls, dat, pos):
        """Find a repeatable block in the data.

        Part of the literal port of the Pico-8 compression routine. See
        compress_code().

        Args:
          dat: array of data bytes
          pos: starting index in dat
        """
        max_block_len = 17
        max_hist_len = (255 - len(COMPRESSED_LUA_CHAR_TABLE)) * 16
        best_len = 0
        best_i = -100000

        max_len = min(max_block_len, len(dat) - pos)
        max_hist_len = min(max_hist_len, pos);

        i = pos - max_hist_len
        while i < pos:
            j = i
            while (j - i) < max_len and j < pos and dat[j] == dat[pos + j - i]:
                j += 1

            if (j - i) > best_len:
                best_len = j - i
                best_i = i

            i += 1

        block_offset = pos - best_i

        return best_len, block_offset

    # TODO: Compare this with compress_code_BROKEN and fix the latter.
    @classmethod
    def compress_code(cls, in_p):
        """A literal port of the Pico-8 C compression routine.

        For some reason my looser port in compress_code_BROKEN() does not
        match the original algorithm, so I'm trying a literal port and
        comparing the results. The original algorithm uses a brute force
        search for blocks (_find_repeatable_block()), which makes the overall
        algorithm O(n^2). compress_code_BROKEN() was intended to be faster
        using a block dictionary.

        Args:
          in_p: The code to compress, as a str.

        Returns:
          The compressed code, as a bytearray. The compressed result is
          returned even if it is longer than in_p. The caller is responsible
          for comparing it to the original and acting accordingly.
        """
        PICO8_CODE_ALLOC_SIZE = (0x10000 + 1)
        pos = 0

        literal_index = [0] * 256
        for i in range(1, len(COMPRESSED_LUA_CHAR_TABLE)):
            literal_index[COMPRESSED_LUA_CHAR_TABLE[i]] = i

        if '_update60' in in_p and len(in_p) < PICO8_CODE_ALLOC_SIZE - (
            len(PICO8_FUTURE_CODE2) + 1):
            if in_p[-1] != ' ' and in_p[-1] != '\n':
                in_p += '\n'
            in_p += PICO8_FUTURE_CODE2

        out = bytearray()

        # The Pico-8 C code adds the preamble here, but we do it in
        # get_bytes_from_code().
        #out += b':c:\x00'
        #out.append(len(in_p) // 256)
        #out.append(len(in_p) % 256)
        #out += b'\x00\x00'

        while pos < len(in_p):
            block_len, block_offset = cls._find_repeatable_block(in_p, pos)

            if block_len >= 3:
                out.append(
                    (block_offset // 16) + len(COMPRESSED_LUA_CHAR_TABLE))
                out.append((block_offset % 16) + (block_len - 2) * 16)
                pos += block_len
            else:
                out.append(literal_index[ord(in_p[pos])])
                if literal_index[ord(in_p[pos])] == 0:
                    out.append(ord(in_p[pos]))
                pos += 1

        return out

    @classmethod
    def decompress_code(cls, codedata):
        """Decompresses compressed code data.

        Args:
          codedata: The bytes of the code region (0x4300:0x8000).

        Returns:
          The tuple (code_length, code, compressed_size).
        """
        code_length = (codedata[4] << 8) | codedata[5]
        assert bytes(codedata[6:8]) == b'\x00\x00'

        out = [0] * code_length
        in_i = 8
        out_i = 0
        while out_i < code_length and in_i < len(codedata):
            if codedata[in_i] == 0x00:
                in_i += 1
                out[out_i] = codedata[in_i]
                out_i += 1
            elif codedata[in_i] <= 0x3b:
                out[out_i] = COMPRESSED_LUA_CHAR_TABLE[codedata[in_i]]
                out_i += 1
            else:
                in_i += 1
                offset = ((codedata[in_i - 1] - 0x3c) * 16 +
                          (codedata[in_i] & 0xf))
                length = (codedata[in_i] >> 4) + 2
                out[out_i:out_i + length] = \
                    out[out_i - offset:out_i - offset + length]
                out_i += length
            in_i += 1

        code = ''.join(chr(c) for c in out)
        if code.endswith(PICO8_FUTURE_CODE2):
            code = code[:-len(PICO8_FUTURE_CODE2)]
            if code[-1] == '\n':
                code = code[:-1]

        compressed_size = in_i

        return code_length, code, compressed_size

    @classmethod
    def get_code_from_bytes(cls, codedata, version):
        """Gets the code text from the byte data.

        Args:
          codedata: The bytes of the code region (0x4300:0x8000).
          version: The version of the cart data.

        Returns:
          The tuple (code_length, code, compressed_size). compressed_size is
          None if the code data was not compressed.
        """

        if version == 0 or bytes(codedata[:4]) != b':c:\x00':
            # code is ASCII

            try:
                code_length = codedata.index(0)
            except ValueError:
                # Edge case: uncompressed code completely fills the code area.
                code_length = 0x8000 - 0x4300

            code = ''.join(chr(c) for c in codedata[:code_length]) + '\n'
            compressed_size = None

        else:
            # code is compressed
            code_length, code, compressed_size = cls.decompress_code(codedata)

        code = code.replace('\r', ' ')

        return code_length, code, compressed_size

    @classmethod
    def get_bytes_from_code(cls, code):
        """Gets the byte data for code text.

        Args:
          code: The code text.

        Returns:
          The bytes for the code, possibly compressed.
        """
        compressed_bytes = cls.compress_code(code)
        if len(compressed_bytes) < len(code):
            # Use compressed.
            code_length_bytes = bytes([len(code) >> 8, len(code) & 255])
            code_bytes = b''.join([b':c:\0', code_length_bytes, b'\0\0',
                                   compressed_bytes])
        else:
            # Use uncompressed.
            code_bytes = bytes(code, 'utf-8')

        byte_array = bytearray(0x8000-0x4300)
        byte_array[:len(code_bytes)] = code_bytes

        return byte_array

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
        try:
            r = png.Reader(file=instr)
            (width, height, data, attrs) = r.read()
            data = list(data)
        except png.Error:
            raise InvalidP8PNGError()

        picodata = cls.get_picodata_from_pngdata(width, height, data, attrs)

        gfx = picodata[0x0:0x2000]
        p8map = picodata[0x2000:0x3000]
        gfx_props = picodata[0x3000:0x3100]
        song = picodata[0x3100:0x3200]
        sfx = picodata[0x3200:0x4300]
        codedata = picodata[0x4300:0x8000]
        version = picodata[0x8000]

        # TODO: Extract new_game.label from data

        (code_length, code, compressed_size) = cls.get_code_from_bytes(
            codedata, version)

        new_game = cls(filename=filename, compressed_size=compressed_size)
        new_game.version = version
        new_game.lua = Lua.from_lines(
            [code], version=version)
        new_game.gfx = Gfx.from_bytes(
            gfx, version=version)
        new_game.gff = Gff.from_bytes(
            gfx_props, version=version)
        new_game.map = Map.from_bytes(
            p8map, version=version, gfx=new_game.gfx)
        new_game.sfx = Sfx.from_bytes(
            sfx, version=version)
        new_game.music = Music.from_bytes(
            song, version=version)

        return new_game

    def get_compressed_size(self):
        """Gets the compressed code size.

        If the code was not already stored compressed, this runs the
        compression routine to determine the size it would be if compressed.

        Returns:
          The compressed code size, as a number of bytes.
        """
        if self.compressed_size is not None:
            return self.compressed_size
        comp_result = self.compress_code(''.join(self.lua.to_lines()))
        return len(comp_result)

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

        outstr.write(HEADER_VERSION_PAT.format(8))

        # Sanity-check the Lua written by the writer.
        transformed_lua = Lua.from_lines(
            self.lua.to_lines(writer_cls=lua_writer_cls,
                              writer_args=lua_writer_args),
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

        outstr.write(SECTION_DELIM_PAT.format('lua'))
        # There is surely a better way to check this:
        if lua_writer_cls == LuaMinifyTokenWriter:
            # Of course, the above char count is now off.
            if self.title:
                outstr.write('--' + self.title)
            if self.byline:
                outstr.write('--' + self.byline)

        ended_in_newline = None
        lbuffer = ''
        char_count = 0
        transformed_char_count = transformed_lua.get_char_count()
        for l in self.lua.to_lines(writer_cls=lua_writer_cls,
                                   writer_args=lua_writer_args):
            ended_in_newline = l.endswith('\n')
            lbuffer += l
            char_count += len(l)
            if ended_in_newline or char_count == transformed_char_count:
                # Last-chance fix to edge cases needing spaces around arithmetic assignments.
                # Regex for this is a lot simpler than I was first testing,
                # but no guarantees on it working for all cases.
                # "[^\s\)]|\)[^a-z]" means no spaces and no ")" unless it is a ")" followed by
                # something other than a letter.  In other words, ingore "()" if used on
                # the left side (possible?), but if ")" is the last char of the previous
                # statement, then that is okay (which would look like: "...)someletter+=..." ).
                #
                # Left, then right, separately.  (Can't use re.finditer due to expansion.)
                while True:
                    m = re.search(r'(\]|\})[a-z]([^\s\)]|\)[^a-z]| and | or |not )*(\+=|-=|\*=|\/=|%=)', lbuffer)
                    if m:
                        lbuffer = lbuffer[:m.start()+1] + ' ' + lbuffer[m.start()+1:]
                        #print(lbuffer)
                    else:
                        break
                while True:
                    m = re.search(r'(\+=|-=|\*=|\/=|%=)(\S| and | or |not )*(\]|\))[a-z]', lbuffer)
                    if m:
                        lbuffer = lbuffer[:m.end()-1] + ' ' + lbuffer[m.end()-1:]
                        #print(lbuffer)
                    else:
                        break
                outstr.write(lbuffer)
                lbuffer = ''
            #outstr.write(l)
            #ended_in_newline = l.endswith('\n')
        if not ended_in_newline:
            outstr.write('\n')

        outstr.write(SECTION_DELIM_PAT.format('gfx'))
        for l in self.gfx.to_lines():
            outstr.write(l)

        if self.label:
            outstr.write(SECTION_DELIM_PAT.format('label'))
            for l in self.label.to_lines():
                outstr.write(l)

        # Pico-8 emits an extra newline before __gff__ for no good reason, as of 0.1.10c.
        outstr.write('\n')
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

    def to_p8png_file(self, outstr, label_fname=None, lua_writer_cls=None,
                      lua_writer_args=None, filename=None):
        """Write the game data as a .p8.png file.

        Args:
          outstr: The output stream.
          label_fname: The .p8.png file (or appropriately spec'd .png file)
            to use for the label. If None, uses a Pico-8-generated empty label.
          lua_writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          lua_writer_args: Args to pass to the Lua writer.
          filename: The output filename, for error messages.
        """
        # To install: python3 -m pip install pypng
        import png

        # TODO: If self.label, use EMPTY_LABEL_FNAME and substitute the appropriate img_data
        label_fname = label_fname or EMPTY_LABEL_FNAME
        try:
            with open(label_fname, 'rb') as label_fh:
                r = png.Reader(file=label_fh)
                (width, height, img_data, attrs) = r.read()
                img_data = list(img_data)
        except png.Error:
            raise InvalidP8PNGError()

        cart_lua = self.lua.to_lines(writer_cls=lua_writer_cls,
                                     writer_args=lua_writer_args)
        code_bytes = self.get_bytes_from_code(''.join(cart_lua))

        picodata = b''.join((self.gfx.to_bytes(),
                         self.map.to_bytes(),
                         self.gff.to_bytes(),
                         self.music.to_bytes(),
                         self.sfx.to_bytes(),
                         code_bytes,
                         bytes((self.version,))))

        new_rows = self.get_pngdata_from_picodata(picodata, img_data, attrs)

        wr = png.Writer(width, height, **attrs)
        wr.write(outstr, new_rows)

    def to_file(self, filename=None, *args, **kwargs):
        """Write the game data to a file, based on a filename.

        If filename ends with .png, the output is a .p8.png file. If the
        output file exists, its label is reused, otherwise an empty label is
        used. The label can be overridden by the caller with the
        'label_fname' argument.

        If filename does not end with .png, then the output is a .p8 file.

        Args:
            filename: The filename.
        """
        if filename.endswith('.png'):
            file_args = {'mode':'wb+'}
        else:
            file_args = {'mode':'w+', 'encoding':'iso-8859-1'}
        with tempfile.TemporaryFile(**file_args) as outfh:
            if filename.endswith('.png'):
                if kwargs.get('label_fname', None) is None:
                    if os.path.exists(filename):
                        kwargs['label_fname'] = filename
                self.to_p8png_file(outfh, filename=filename, *args, **kwargs)
            else:
                self.to_p8_file(outfh, *args, **kwargs)
            outfh.seek(0)
            with open(filename, **file_args) as finalfh:
                finalfh.write(outfh.read())

    def write_cart_data(self, data, start_addr=0):
        """Write binary data to an arbitrary cart address.

        Args:
            data: The data to write, as a byte string or bytearray.
            start_addr: The address to start writing.
        """
        if start_addr + len(data) > 0x4300:
            raise ValueError('Data too large: {} bytes starting at {} exceeds '
                             '0x4300'.format(len(data), start_addr))
        memmap = ((0x0,0x2000,self.gfx._data),
          (0x2000,0x3000,self.map._data),
          (0x3000,0x3100,self.gff._data),
          (0x3100,0x3200,self.music._data),
          (0x3200,0x4300,self.sfx._data))
        for start_a, end_a, section_data in memmap:
            if (start_addr > end_a or
                  start_addr + len(data) < start_a):
                continue
            data_start_a = (start_addr - start_a
                            if start_addr > start_a
                            else 0)
            data_end_a = (start_addr + len(data) - start_a
                          if start_addr + len(data) < end_a
                          else end_a)
            text_start_a = (0 if start_addr > start_a
                            else start_a - start_addr)
            text_end_a = (len(data)
                          if start_addr + len(data) < end_a
                          else -(start_addr + len(data) - end_a))
            section_data[data_start_a:data_end_a] = \
                data[text_start_a:text_end_a]
