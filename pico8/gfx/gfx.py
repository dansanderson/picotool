"""The sprite graphics section of a Pico-8 cart.

The graphics region consists of 8192 bytes. The .p8 representation is
128 lines of 128 hexadecimal digits (64 bytes).

The in-memory representation is similar, but with nibble-pairs
swapped. (The .p8 representation resembles pixel left-to-right
ordering, while the RAM representation uses the most significant
nibble for the right pixel of each pixel pair.)
"""

__all__ = ['Gfx']

from .. import util


# Constants for the Pico-8 color values.
BLACK = 0
DARK_BLUE = 1
DARK_PURPLE = 2
DARK_GREEN = 3
BROWN = 4
DARK_GRAY = 5
LIGHT_GRAY = 6
WHITE = 7
RED = 8
ORANGE = 9
YELLOW = 10
GREEN = 11
BLUE = 12
INDIGO = 13
PINK = 14
PEACH = 15

# A special color value accepted by set_sprite() to leave an existing pixel on
# the spritesheet unchanged.
TRANSPARENT = 16


class Gfx(util.BaseSection):
    """The sprite graphics section for a Pico-8 cart."""
    HEX_LINE_LENGTH_BYTES = 64

    @classmethod
    def empty(cls, version=4):
        """Creates an empty instance.

        Returns:
          A Gfx instance.
        """
        return cls(data=bytearray(b'\x00' * 128 * 64), version=version)
    
    @classmethod
    def from_lines(cls, lines, version):
        """Create an instance based on .p8 data lines.

        The base implementation reads lines of ASCII-encoded hexadecimal bytes.

        Args:
          lines: .p8 lines for the section.
          version: The Pico-8 data version from the game file header.

        Returns:
          A Gfx instance.
        """
        datastrs = []
        for l in lines:
            if len(l) != 129:
                continue
            
            larray = list(l.rstrip())
            for i in range(0,128,2):
                (larray[i], larray[i+1]) = (larray[i+1], larray[i])

            datastrs.append(bytearray.fromhex(''.join(larray)))

        data = b''.join(datastrs)
        return cls(data=data, version=version)

    def to_lines(self):
        """Generates lines of ASCII-encoded hexadecimal strings.

        The .p8 for the gfx section writes data bytes with the nibbles
        (4-bits) swapped to represent pixel order.

        Yields:
          One line of a hex string.
        """
        for start_i in range(0, len(self._data), self.HEX_LINE_LENGTH_BYTES):
            end_i = start_i + self.HEX_LINE_LENGTH_BYTES
            newdata = []
            for b in self._data[start_i:end_i]:
                newdata.append((b & 0x0f) << 4 | (b & 0xf0) >> 4)
                
            yield bytes(newdata).hex() + '\n'

    def get_sprite(self, id, tile_width=1, tile_height=1):
        """Retrieves the graphics data for a sprite.

        The return value is a list of bytearrays, where each bytearray
        represents a row of pixels. Each value is a color value for a
        pixel (0-15).

        By default, this returns a sprite consisting of the tile with
        the given Pico-8 tile ID, an 8x8 pixel region. You can request
        multiple tiles in a single sprite using the tile_width and
        tile_height arguments. The complete sprite is calculated from
        the 16 tile x 16 tile spritesheet with the tile of the given
        ID in the upper left corner, similar to the Pico-8 spr
        function. If the given width or height extend off the edge of
        the spritesheet, the extraneous space is filled with zeroes.

        Pico-8 tile IDs start with 0 in the upper left corner, and
        increase left to right, then top to bottom, in the 16 tile x
        16 tile spritesheet.

        Args:
          id: The Pico-8 tile ID that is the upper-left corner of the requested
            sprite.
          tile_width: The width of the requested sprite, as a number of tiles.
            Must be 1 or greater.
          tile_height: The height of the requested sprite, as a number of tiles.
            Must be 1 or greater.

        Returns:
          A list of bytearrays, one bytearray per row, where each cell
          is a color from 0 (transparent/black) to 15 (peach). (See
          the color constants defined in the gfx module.)
        """
        assert 0 <= id <= 255
        assert 1 <= tile_width
        assert 1 <= tile_height
        first_tile_row = id // 16
        first_tile_col = id % 16
        result = []
        for ty in range(first_tile_row, first_tile_row + tile_height):
            for y_offset in range(8):
                row = bytearray()
                for tx in range(first_tile_col, first_tile_col + tile_width):
                    if tx > 15 or ty > 15:
                        row.extend([0] * 8)
                    else:
                        for x_offset in range(8):
                            data_loc = (ty * 64 * 8 +
                                        y_offset * 64 +
                                        tx * 4 +
                                        x_offset // 2)
                            b = self._data[data_loc]
                            if x_offset % 2 == 0:
                                row.append(b & 0x0f)
                            else:
                                row.append((b & 0xf0) >> 4)
                result.append(row)
        return result

    def set_sprite(self, id, sprite, tile_x_offset=0, tile_y_offset=0):
        """Sets pixel data in the spritesheet.

        The given sprite pattern is drawn onto the spritesheet using
        the given tile ID as the upper left corner of the sprite. The
        sprite data is an iterable (rows) of iterables (columns) of
        bytes (pixel colors), similar to the data structure returned
        by get_sprite(). The pixels are drawn onto the 16 tile x 16
        tile spritesheet. If the given sprite data extends to the
        right or below the spritesheet, the excess is clipped.

        To draw the given sprite data offset from the upper left
        corner of a tile, specify a non-zero tile_x_offset or
        tile_y_offset.

        If a pixel value is gfx.TRANSPARENT, the existing pixel data
        in that location is preserved. A pixel value of gfx.BLACK
        overwrites the pixel (even though "black" is transparent by
        default when blitting sprites in Pico-8).

        All rows of the sprite data are assumed to be
        left-aligned. Rows can be of different lengths to leave pixels
        to the right of each row unchanged. To leave pixels on the
        left side of a row unchanged, use gfx.TRANSPARENT values.

        Using a combination of these features, it is possible to paint
        graphics data of an arbitrary shape at an arbitrary location
        on the spritesheet.

        Args:
          id: The Pico-8 tile ID that is the upper-left corner of the requested
            sprite.
          sprite: The sprite pixel data, as an iterable of iterables of pixel 
            color values.
          tile_x_offset: If non-zero, start drawing the sprite data onto the
            spritesheet this many pixels to the right of the left edge of the
            tile with the given ID.
          tile_y_offset: If non-zero, start drawing the sprite data onto the
            spritesheet this many pixels below the top edge of the tile with
            the given ID.
        """
        first_tile_row = id // 16
        first_tile_col = id % 16
        first_x_coord = first_tile_col * 8 + tile_x_offset
        first_y_coord = first_tile_row * 8 + tile_y_offset
        for y, row in enumerate(sprite):
            for x, val in enumerate(row):
                if ((val == TRANSPARENT) or
                    ((first_y_coord + y) > 128) or
                    ((first_x_coord + x) > 128)):
                    continue
                data_loc = (first_y_coord + y) * 64 + (first_x_coord + x) // 2
                b = self._data[data_loc]
                if (first_x_coord + x) % 2 == 0:
                    b = (b & 0xf0) + val
                else:
                    b = (b & 0x0f) + (val << 4)
                self._data[data_loc] = b
