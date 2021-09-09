"""The map section of a PICO-8 cart.

The map region consists of 4096 bytes. The .p8 representation is 32
lines of 256 hexadecimal digits (128 bytes).

The map is 128 tiles wide by 64 tiles high. Each tile is one of the
256 tiles from the spritesheet. Map memory describes the top 32 rows
(128 * 32 = 4096). If the developer draws tiles in the bottom 32 rows,
this is stored in the bottom of the gfx memory region.
"""

__all__ = ['Map']

from .. import util


class Map(util.BaseSection):
    """The map region of a PICO-8 cart."""
    HEX_LINE_LENGTH_BYTES = 128

    def __init__(self, *args, **kwargs):
        """The initializer.

        The Map initializer takes an optional gfx keyword argument
        whose value is a reference to the Gfx instance where lower map
        data is stored.
        """
        self._gfx = None
        if 'gfx' in kwargs:
            self._gfx = kwargs['gfx']
            del kwargs['gfx']
        super().__init__(*args, **kwargs)

    @classmethod
    def empty(cls, version=4, gfx=None):
        """Creates an empty instance.

        Args:
          version: The PICO-8 file version.
          gfx: The Gfx object where lower map data is written.

        Returns:
          A Map instance.
        """
        return cls(data=bytearray(b'\x00' * 4096), version=version, gfx=gfx)

    @classmethod
    def from_lines(cls, *args, **kwargs):
        gfx = None
        if 'gfx' in kwargs:
            gfx = kwargs['gfx']
            del kwargs['gfx']
        result = super().from_lines(*args, **kwargs)
        result._gfx = gfx
        return result

    @classmethod
    def from_bytes(cls, *args, **kwargs):
        gfx = None
        if 'gfx' in kwargs:
            gfx = kwargs['gfx']
            del kwargs['gfx']
        result = super().from_bytes(*args, **kwargs)
        result._gfx = gfx
        return result

    def get_cell(self, x, y):
        """Gets the tile ID for a map cell.

        Args:
          x: The map cell x (column) coordinate. (0-127)
          y: The map cell y (row) coordinate. Map must have a Gfx if y > 31.
            (0-63)

        Returns:
          The tile ID for the cell.
        """
        assert 0 <= x <= 127
        assert (0 <= y <= 31) or ((0 <= y <= 63) and self._gfx is not None)
        if y <= 31:
            return self._data[y * 128 + x]
        return self._gfx._data[4096 + (y - 32) * 128 + x]

    def set_cell(self, x, y, val):
        """Sets the tile ID for a map cell.

        Args:
          x: The map cell x (column) coordinate. (0-127)
          y: The map cell y (row) coordinate. (0-63) If y > 31, Map must have a
            Gfx, and this method updates the shared data region in the Gfx.
          val: The new tile ID for the cell. (0-255)
        """
        assert 0 <= x <= 127
        assert (0 <= y <= 31) or ((0 <= y <= 63) and self._gfx is not None)
        assert 0 <= val <= 255
        if y <= 31:
            self._data[y * 128 + x] = val
        else:
            self._gfx._data[4096 + (y - 32) * 128 + x] = val

    def get_rect_tiles(self, x, y, width=1, height=1):
        """Gets a rectangle of map tiles.

        The map is a grid of 128x32 tiles, or 128x64 if using the
        gfx/map shared memory for map data. This method returns a
        rectangle of tile IDs on the map, as a list of bytearrays.

        If the requested rectangle size goes off the edge of the map,
        the off-edge tiles are returned as 0. The bottom edge is
        always assumed to be beyond the 64th row in the gfx/map shared
        memory region.

        Args:
          x: The map cell x (column) coordinate. (0-127)
          y: The map cell y (row) coordinate. (0-63) If y + height > 31, Map
            must have a Gfx.
          width: The width of the rectangle, as a number of tiles.
          height: The height of the rectangle, as a number of tiles.

        Returns:
          The rectangle of tile IDs, as a list of bytearrays.
        """
        assert 0 <= x <= 127
        assert 1 <= width
        assert 1 <= height
        assert ((0 <= y + height <= 32) or
                ((0 <= y + height <= 64) and self._gfx is not None))
        result = []
        for tile_y in range(y, y + height):
            row = bytearray()
            for tile_x in range(x, x + width):
                if (tile_y > 63) or (tile_x > 127):
                    row.append(0)
                else:
                    row.append(self.get_cell(tile_x, tile_y))
            result.append(row)
        return result

    def set_rect_tiles(self, rect, x, y):
        """Writes a rectangle of tiles to the map.

        If writing the given rectangle at the given coordinates causes
        the rectangle to extend off the edge of the map, the remainer
        is discarded.

        Args:
          rect: A rectangle of tile IDs, as an iterable of iterables of IDs.
          x: The map tile x coordinate (column) of the upper left corner to
            start writing.
          y: The map tile y coordinate (row) of the upper left corner to
            start writing.
        """
        for tile_y, row in enumerate(rect):
            for tile_x, val in enumerate(row):
                if ((tile_y + y) > 127) or ((tile_x + x) > 127):
                    continue
                self.set_cell(tile_x + x, tile_y + y, val)

    def get_rect_pixels(self, x, y, width=1, height=1):
        """Gets a rectangel of map tiles as pixels.

        This is similar to get_rect_tiles() except the tiles are
        extracted from Gfx data and returned as a rectangle of pixels.

        Just like PICO-8, tile ID 0 is rendered as empty (all 0's),
        not the actual tile at ID 0.

        Args:
          x: The map cell x (column) coordinate. (0-127)
          y: The map cell y (row) coordinate. (0-63) If y + height > 31, Map
            must have a Gfx.
          width: The width of the rectangle, as a number of tiles.
          height: The height of the rectangle, as a number of tiles.

        Returns:
          The rectangle of pixels, as a list of bytearrays of pixel colors.

        """
        assert self._gfx is not None
        assert 0 <= x <= 127
        assert 1 <= width
        assert 1 <= height
        assert 0 <= y + height <= 64
        tile_rect = self.get_rect_tiles(x, y, width, height)
        result = []
        for tile_row in tile_rect:
            pixel_row = [bytearray(), bytearray(), bytearray(), bytearray(),
                         bytearray(), bytearray(), bytearray(), bytearray()]
            for id in tile_row:
                if id == 0:
                    sprite = [bytearray(b'\x00' * 8)] * 8
                else:
                    sprite = self._gfx.get_sprite(id)
                for i in range(0, 8):
                    pixel_row[i].extend(sprite[i])
            for i in range(0, 8):
                result.append(pixel_row[i])
        return result
