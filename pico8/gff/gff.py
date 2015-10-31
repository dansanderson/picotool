"""The graphics flags section of a Pico-8 cart.

The graphics properties region consists of 256 bytes. The .p8
representation is 2 lines of 256 hexadecimal digits (128 bytes).

This represents eight flags for each of the 256 tiles in the main gfx
area. In the graphics editor, the flags are arranged left to right
from LSB to MSB: red=1, orange=2, yellow=4, green=8, blue=16, purple=32,
pink=64, peach=128.

"""

__all__ = ['Gff']

from .. import util


# Constants for flags.
RED = 1
ORANGE = 2
YELLOW = 4
GREEN = 8
BLUE = 16
PURPLE = 32
PINK = 64
PEACH = 128
ALL = 255


class Gff(util.BaseSection):
    """The graphics properties section of a Pico-8 cart."""
    HEX_LINE_LENGTH_BYTES = 128

    @classmethod
    def empty(cls, version=4):
        """Create an empty instance.

        Returns:
          A Gff instance.
        """
        return cls(data=bytearray(b'\x00' * 256), version=version)

    def get_flags(self, id, flags):
        """Gets the value of a specific flag or flags.

        Given a tile ID and a flag, returns the value of the flag if
        it is set, or zero otherwise:
          if gff_obj.get_flags(0, BLUE):
              # The blue flag is set.

        You can bitwise-or (|) flag constants together to get more
        than one with a single call. The result is all of the set
        flags bitwise-or'd together:
          is_set = gff_obj.get_flags(0, RED | BLUE | PEACH)
          if is_set | BLUE:
              # The blue flag is set.

        Call with the ALL constant to get all flags in a single value.
          flags = gff_obj.get_flags(0, ALL)
        """
        assert 0 <= id <= 255
        return self._data[id] & flags
    
    def set_flags(self, id, flags):
        """Sets one or more flags for a tile.

        This sets the specified flags, and leaves the other flags unchanged.

        You can bitwise-or (|) flag constants together to set more than one with
        a single call:
          gff_obj.set_flags(0, RED | BLUE | PEACH)

        Args:
          id: The Pico-8 ID of the tile (0-255).
          flags: The flags to set, bitwise-or'd together.
        """
        assert 0 <= id <= 255
        self._data[id] |= (flags & ALL)

    def clear_flags(self, id, flags):
        """Clears one or more flags for a tile.

        This clears the specified flags, and leaves the other flags unchanged.

        You can bitwise-or (|) flag constants together to clear more than one
        with a single call:
          gff_obj.clear_flags(0, RED | BLUE | PEACH)

        Args:
          id: The Pico-8 ID of the tile (0-255).
          flags: The flags to clear, bitwise-or'd together.
        """
        assert 0 <= id <= 255
        self._data[id] &= (~flags & ALL)

    def reset_flags(self, id, flags):
        """Resets all flags for a tile, then sets the given flags.

        This changes all flags for the tile so that only the specified flags are
        set.

        Args:
          id: The Pico-8 ID of the tile (0-255).
          flags: All flags to be set in the final state, bitwise-or'd together.
        """
        assert 0 <= id <= 255
        self._data[id] = flags & ALL
