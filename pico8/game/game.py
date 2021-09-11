"""A container for a PICO-8 game, and routines to load and save game files."""

__all__ = [
    'DEFAULT_VERSION',
    'Game',
]


from . import compress
from ..lua.lua import Lua
from ..gfx.gfx import Gfx
from ..gff.gff import Gff
from ..map.map import Map
from ..sfx.sfx import Sfx
from ..music.music import Music


DEFAULT_VERSION = 33


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

    def get_compressed_size(self):
        """Gets the compressed code size.

        If the code was not already stored compressed, this runs the
        compression routine to determine the size it would be if compressed.

        Returns:
          The compressed code size, as a number of bytes.
        """
        if self.compressed_size is not None:
            return self.compressed_size
        comp_result = compress.compress_code(b''.join(self.lua.to_lines()))
        return len(comp_result)

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
