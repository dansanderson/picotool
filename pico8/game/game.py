"""A container for a PICO-8 game, and routines to load and save game files."""

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
from ..lua.lua import Lua, unicode_to_p8scii, p8scii_to_unicode
from ..lua.lua import PICO8_LUA_CHAR_LIMIT
from ..lua.lua import PICO8_LUA_TOKEN_LIMIT
from ..gfx.gfx import Gfx
from ..gff.gff import Gff
from ..map.map import Map
from ..sfx.sfx import Sfx
from ..music.music import Music

HEADER_TITLE_STR = b'pico-8 cartridge // http://www.pico-8.com\n'
HEADER_VERSION_RE = re.compile(br'version (\d+)\n')
SECTION_DELIM_RE = re.compile(br'__(\w+)__\n')

DEFAULT_VERSION = 8
EMPTY_LABEL_FNAME = os.path.join(os.path.dirname(__file__), 'empty_018.p8.png')
COMPRESSED_LUA_CHAR_TABLE = list(
    b'#\n 0123456789abcdefghijklmnopqrstuvwxyz!#%(){}[]<>+=/*:;.,~_')

# PICO-8 adds this automatically to compressed code and removes it
# automatically from decompressed code to maintain compatibility with PICO-8
# 0.1.7.
PICO8_FUTURE_CODE1 = (b'if(_update60)_update=function()'
                      b'_update60()_update60()end')
PICO8_FUTURE_CODE2 = (b'if(_update60)_update=function()'
                      b'_update60()_update_buttons()_update60()end')


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
    """A PICO-8 game."""

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
          filename: The name of the file. Must end in either ".p8" or
            ".p8.png".

        Returns:
          A Game containing the game data.

        Raises:
          lexer.LexerError
          parser.ParserError
          InvalidP8HeaderError
        """
        assert filename.endswith('.p8.png') or filename.endswith('.p8')
        if filename.endswith('.p8'):
            with open(filename, 'rb') as fh:
                g = Game.from_p8_file(fh, filename=filename)
        else:
            with open(filename, 'rb') as fh:
                g = Game.from_p8png_file(fh, filename=filename)
        return g

    @classmethod
    def get_raw_data_from_p8_file(cls, instr, filename=None):
        header_title_str = instr.readline()
        if header_title_str != HEADER_TITLE_STR:
            raise InvalidP8HeaderError()
        header_version_str = instr.readline()
        version_m = HEADER_VERSION_RE.match(header_version_str)
        if version_m is None:
            raise InvalidP8HeaderError()
        version = int(version_m.group(1))

        # (section is a text str.)
        section = None
        section_lines = {}
        while True:
            line = instr.readline()
            if not line:
                break
            section_delim_m = SECTION_DELIM_RE.match(line)
            if section_delim_m:
                section = str(section_delim_m.group(1), encoding='utf-8')
                section_lines[section] = []
            elif section:
                p8scii_line = unicode_to_p8scii(
                    str(line, encoding='utf-8'))
                section_lines[section].append(p8scii_line)

        class P8Data(object):
            pass
        data = P8Data()
        data.version = version
        data.section_lines = section_lines

        return data

    @classmethod
    def from_p8_file(cls, instr, filename=None):
        """Loads a game from a .p8 file.

        Args:
          instr: The binary input stream.
          filename: The filename, if any, for tool messages.

        Returns:
          A Game containing the game data.

        Raises:
          InvalidP8HeaderError
        """
        data = cls.get_raw_data_from_p8_file(instr, filename=filename)

        new_game = cls.make_empty_game(filename=filename)
        # Discard empty label until one is found in the file.
        new_game.label = None
        new_game.version = data.version
        for section in data.section_lines:
            if section == 'lua':
                new_game.lua = Lua.from_lines(
                    data.section_lines[section], version=data.version)
            elif section == 'gfx':
                new_game.gfx = Gfx.from_lines(
                    data.section_lines[section], version=data.version)
                my_map = getattr(new_game, 'map')
                if my_map is not None:
                    my_map._gfx = new_game.gfx
            elif section == 'gff':
                new_game.gff = Gff.from_lines(
                    data.section_lines[section], version=data.version)
            elif section == 'map':
                my_gfx = getattr(new_game, 'gfx')
                new_game.map = Map.from_lines(
                    data.section_lines[section],
                    version=data.version,
                    gfx=my_gfx)
            elif section == 'sfx':
                new_game.sfx = Sfx.from_lines(
                    data.section_lines[section], version=data.version)
            elif section == 'music':
                new_game.music = Music.from_lines(
                    data.section_lines[section], version=data.version)
            elif section == 'label':
                new_game.label = Gfx.from_lines(
                    data.section_lines[section], version=data.version)
            else:
                raise InvalidP8SectionError(section)

        return new_game

    @classmethod
    def get_picodata_from_pngdata(cls, width, height, pngdata, attrs):
        """Extracts PICO-8 bytes from a .p8.png's PNG data.

        The arguments are expected in the format returned by png.Reader's
        read() method.

        Args:
          width: The PNG width.
          height: The PNG height.
          pngdata: The PNG data region, an iterable of 'height' rows, where
            each row is an indexable 'width' * 'attrs['planes']' long.
          attrs: The PNG attrs.

        Returns:
          The PICO-8 data, a list of width * height (0x8000) byte-size numbers.
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
        """Encodes PICO-8 bytes into a given PNG's image data.

        Args:
          picodata: The PICO-8 data, a bytearray of 0x8000 bytes.
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

    @classmethod
    def _find_repeatable_block(cls, dat, pos):
        """Find a repeatable block in the data.

        Part of the literal port of the PICO-8 compression routine. See
        compress_code().

        Args:
            dat: Array of data bytes.
            pos: Starting index in dat.

        Returns:
            A tuple: (best_len, block_offset)
        """
        max_block_len = 17
        max_hist_len = (255 - len(COMPRESSED_LUA_CHAR_TABLE)) * 16
        best_len = 0
        best_i = -100000

        max_len = min(max_block_len, len(dat) - pos)
        max_hist_len = min(max_hist_len, pos)

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

    @classmethod
    def compress_code(cls, in_p):
        """A literal port of the PICO-8 C compression routine.

        TODO: The original algorithm uses a brute force search for blocks
        (_find_repeatable_block()), which makes the overall algorithm O(n^2).
        I had a previous implementation that was faster but did not produce
        the same compressed result. It should be possible to optimize the
        working implementation using Python features without changing its
        result. (A quick attempt at memoization did not result in a speed
        increase.)

        Args:
          in_p: The code to compress, as a bytestring.

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

        if b'_update60' in in_p and len(in_p) < PICO8_CODE_ALLOC_SIZE - (
                len(PICO8_FUTURE_CODE2) + 1):
            if in_p[-1] != b' '[0] and in_p[-1] != b'\n'[0]:
                in_p += b'\n'
            in_p += PICO8_FUTURE_CODE2

        out = bytearray()

        # The PICO-8 C code adds the preamble here, but we do it in
        # get_bytes_from_code().
        # out += b':c:\x00'
        # out.append(len(in_p) // 256)
        # out.append(len(in_p) % 256)
        # out += b'\x00\x00'

        while pos < len(in_p):
            block_len, block_offset = cls._find_repeatable_block(in_p, pos)

            if block_len >= 3:
                out.append(
                    (block_offset // 16) + len(COMPRESSED_LUA_CHAR_TABLE))
                out.append((block_offset % 16) + (block_len - 2) * 16)
                pos += block_len
            else:
                out.append(literal_index[in_p[pos]])
                if literal_index[in_p[pos]] == 0:
                    out.append(in_p[pos])
                pos += 1

        return out

    @classmethod
    def decompress_code(cls, codedata):
        """Decompresses compressed code data.

        Args:
          codedata: The bytes of the code region (0x4300:0x8000).

        Returns:
          The tuple (code_length, code, compressed_size). code is a bytestring.
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

        code = bytes(out).strip(b'\x00')
        if code.endswith(PICO8_FUTURE_CODE1):
            code = code[:-len(PICO8_FUTURE_CODE1)]
            if code[-1] == b'\n'[0]:
                code = code[:-1]
        if code.endswith(PICO8_FUTURE_CODE2):
            code = code[:-len(PICO8_FUTURE_CODE2)]
            if code[-1] == b'\n'[0]:
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
          None if the code data was not compressed. code is a bytestring.
        """

        if version == 0 or bytes(codedata[:4]) != b':c:\x00':
            # code is ASCII

            try:
                code_length = codedata.index(0)
            except ValueError:
                # Edge case: uncompressed code completely fills the code area.
                code_length = 0x8000 - 0x4300

            code = bytes(codedata[:code_length]) + b'\n'
            compressed_size = None

        else:
            # code is compressed
            code_length, code, compressed_size = cls.decompress_code(codedata)

        code = code.replace(b'\r', b' ')

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
            code_bytes = bytes(code, 'ascii')

        byte_array = bytearray(0x8000-0x4300)
        byte_array[:len(code_bytes)] = code_bytes

        return byte_array

    @classmethod
    def get_raw_data_from_p8png_file(cls, instr, filename=None):
        """Read and unpack raw section data from a .p8.png file.

        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.

        Returns:
          An object with properties of raw data: gfx, p8map, gfx_props,
                  song, sfx, codedata, version, code_length, code,
                  compressed_size.
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

        class ParsedData(object):
            pass
        data = ParsedData()

        data.gfx = picodata[0x0:0x2000]
        data.p8map = picodata[0x2000:0x3000]
        data.gfx_props = picodata[0x3000:0x3100]
        data.song = picodata[0x3100:0x3200]
        data.sfx = picodata[0x3200:0x4300]
        data.codedata = picodata[0x4300:0x8000]
        data.version = picodata[0x8000]

        # TODO: Extract new_game.label from data

        (data.code_length, data.code, data.compressed_size) = \
            cls.get_code_from_bytes(data.codedata, data.version)

        return data

    @classmethod
    def from_p8png_file(cls, instr, filename=None):
        """Loads a game from a .p8.png file.

        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.

        Returns:
          A Game containing the game data.
        """
        data = cls.get_raw_data_from_p8png_file(instr, filename=filename)

        new_game = cls(filename=filename, compressed_size=data.compressed_size)
        new_game.version = data.version
        new_game.lua = Lua.from_lines(
            [data.code], version=data.version)
        new_game.gfx = Gfx.from_bytes(
            data.gfx, version=data.version)
        new_game.gff = Gff.from_bytes(
            data.gfx_props, version=data.version)
        new_game.map = Map.from_bytes(
            data.p8map, version=data.version, gfx=new_game.gfx)
        new_game.sfx = Sfx.from_bytes(
            data.sfx, version=data.version)
        new_game.music = Music.from_bytes(
            data.song, version=data.version)

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
        comp_result = self.compress_code(b''.join(self.lua.to_lines()))
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

        outstr.write(bytes('version %s\n' % self.version, 'utf-8'))

        # Sanity-check the Lua written by the writer.
        transformed_lua = Lua.from_lines(
            self.lua.to_lines(writer_cls=lua_writer_cls,
                              writer_args=lua_writer_args),
            version=(self.version or 0))
        if transformed_lua.get_char_count() > PICO8_LUA_CHAR_LIMIT:
            if filename is not None:
                util.error('{}: '.format(filename))
            util.error('warning: character count {} exceeds the PICO-8 '
                       'limit of {}\n'.format(
                           transformed_lua.get_char_count(),
                           PICO8_LUA_CHAR_LIMIT))
        if transformed_lua.get_token_count() > PICO8_LUA_TOKEN_LIMIT:
            if filename is not None:
                util.error('{}: '.format(filename))
            util.error('warning: token count {} exceeds the PICO-8 '
                       'limit of {}\n'.format(
                           transformed_lua.get_token_count(),
                           PICO8_LUA_TOKEN_LIMIT))

        outstr.write(b'__lua__\n')
        ended_in_newline = None
        for line in self.lua.to_lines(
                writer_cls=lua_writer_cls,
                writer_args=lua_writer_args):
            outstr.write(bytes(p8scii_to_unicode(line), 'utf-8'))
            ended_in_newline = line.endswith(b'\n')
        if not ended_in_newline:
            outstr.write(b'\n')

        outstr.write(b'__gfx__\n')
        for line in self.gfx.to_lines():
            outstr.write(line)

        if self.label:
            outstr.write(b'__label__\n')
            for line in self.label.to_lines():
                outstr.write(line)

        # PICO-8 emits an extra newline before __gff__ for no good reason, as
        # of 0.1.10c. PICO-8 doesn't care whether we do, but our tests want to
        # match the test cart data exactly.
        outstr.write(b'\n')
        outstr.write(b'__gff__\n')
        for line in self.gff.to_lines():
            outstr.write(line)

        outstr.write(b'__map__\n')
        for line in self.map.to_lines():
            outstr.write(line)

        outstr.write(b'__sfx__\n')
        for line in self.sfx.to_lines():
            outstr.write(line)

        outstr.write(b'__music__\n')
        for line in self.music.to_lines():
            outstr.write(line)

        outstr.write(b'\n')

    def to_p8png_file(self, outstr, label_fname=None, lua_writer_cls=None,
                      lua_writer_args=None, filename=None):
        """Write the game data as a .p8.png file.

        Args:
          outstr: The output stream.
          label_fname: The .p8.png file (or appropriately spec'd .png file)
            to use for the label. If None, uses a PICO-8-generated empty label.
          lua_writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          lua_writer_args: Args to pass to the Lua writer.
          filename: The output filename, for error messages.
        """
        # To install: python3 -m pip install pypng
        import png

        # TODO: If self.label, use EMPTY_LABEL_FNAME and substitute the
        # appropriate img_data
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
        code_bytes = self.get_bytes_from_code(b''.join(cart_lua))

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
        file_args = {'mode': 'wb+'}
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
        memmap = ((0x0, 0x2000, self.gfx._data),
                  (0x2000, 0x3000, self.map._data),
                  (0x3000, 0x3100, self.gff._data),
                  (0x3100, 0x3200, self.music._data),
                  (0x3200, 0x4300, self.sfx._data))
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
