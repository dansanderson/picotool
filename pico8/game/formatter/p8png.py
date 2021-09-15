"""File formatter for .p8.png files"""

__all__ = [
    'P8PNGFormatter',
]

import os

from .base import BaseFormatter
from .. import compress
from ..game import Game
from ... import util
from ...lua.lua import Lua
from ...gfx.gfx import Gfx
from ...gff.gff import Gff
from ...map.map import Map
from ...sfx.sfx import Sfx
from ...music.music import Music


EMPTY_LABEL_FNAME = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'empty_023.p8.png')


class InvalidP8PNGError(util.InvalidP8DataError):
    """Exception for PNG parsing errors."""
    pass


def get_picodata_from_pngdata(width, height, pngdata, attrs):
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


def get_pngdata_from_picodata(picodata, pngdata, attrs):
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


def get_code_from_bytes(codedata, version):
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
        code_length, code, compressed_size = \
            compress.decompress_code(codedata)

    code = code.replace(b'\r', b' ')

    return code_length, code, compressed_size


def get_bytes_from_code(code):
    """Gets the byte data for code text.

    Args:
        code: The code text.

    Returns:
        The bytes for the code, possibly compressed.
    """
    compressed_bytes = compress.compress_code(code)
    if len(compressed_bytes) < len(code):
        # Use compressed.
        code_length_bytes = bytes([len(code) >> 8, len(code) & 255])
        code_bytes = b''.join(
            [b':c:\0', code_length_bytes, b'\0\0',
             compressed_bytes])
    else:
        # Use uncompressed.
        code_bytes = bytes(code, 'ascii')

    byte_array = bytearray(0x8000-0x4300)
    byte_array[:len(code_bytes)] = code_bytes

    return byte_array


def get_raw_data_from_p8png_file(instr, filename=None):
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

    picodata = get_picodata_from_pngdata(width, height, data, attrs)

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
        get_code_from_bytes(data.codedata, data.version)

    return data


class P8PNGFormatter(BaseFormatter):
    @classmethod
    def from_file(cls, instr, filename=None, *args, **kwargs):
        """Reads a game from a .p8.png file.

        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.

        Returns:
          A Game containing the game data.
        """
        data = get_raw_data_from_p8png_file(instr, filename=filename)

        new_game = Game(
            filename=filename, compressed_size=data.compressed_size)
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

    @classmethod
    def to_file(
            cls, game, outstr, lua_writer_cls=None,
            lua_writer_args=None, filename=None,
            label_fname=None, *args, **kwargs):
        """Writes a game to a .p8.png file.

        Args:
          game: The Game to write.
          outstr: The output stream.
          lua_writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          lua_writer_args: Args to pass to the Lua writer.
          filename: The output filename, for error messages.
          label_fname: The .p8.png file (or appropriately spec'd .png file)
            to use for the label. If None, uses a PICO-8-generated empty label.
        """
        # To install: python3 -m pip install pypng
        import png

        # TODO: If game.label, use EMPTY_LABEL_FNAME and substitute the
        # appropriate img_data
        label_fname = label_fname or EMPTY_LABEL_FNAME
        try:
            with open(label_fname, 'rb') as label_fh:
                r = png.Reader(file=label_fh)
                (width, height, img_data, attrs) = r.read()
                img_data = list(img_data)
        except png.Error:
            raise InvalidP8PNGError()

        cart_lua = game.lua.to_lines(writer_cls=lua_writer_cls,
                                     writer_args=lua_writer_args)
        code_bytes = get_bytes_from_code(b''.join(cart_lua))

        picodata = b''.join((game.gfx.to_bytes(),
                             game.map.to_bytes(),
                             game.gff.to_bytes(),
                             game.music.to_bytes(),
                             game.sfx.to_bytes(),
                             code_bytes,
                             bytes((game.version,))))

        new_rows = get_pngdata_from_picodata(picodata, img_data, attrs)

        wr = png.Writer(width, height, **attrs)
        wr.write(outstr, new_rows)
