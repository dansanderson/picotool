"""The sprite graphics section of a Pico-8 cart.

The graphics region consists of 8192 bytes. The .p8 representation is
128 lines of 128 hexadecimal digits (64 bytes).
"""
# TODO: more documentaion

__all__ = ['Gfx']

from .. import util

class Gfx(util.BaseSection):
    """The sprite graphics section for a Pico-8 cart."""
    HEX_LINE_LENGTH_BYTES = 64
    
    def to_lines(self):
        """Generates lines of ASCII-encoded hexadecimal strings.

        The .p8 for the gfx section writes data bytes with the nibbles
        (4-bits) swapped to represent pixel order.

        Yields:
          One line of a hex string.
        """
        for start_i in range(0, len(self._data), self.HEX_LINE_LENGTH_BYTES):
            end_i = start_i + self.HEX_LINE_LENGTH_BYTES
            if end_i > len(self._data):
                end_i = len(self._data)

            # gfx writes nibbles in swapped order.
            newdata = []
            for b in self._data[start_i:end_i]:
                newdata.append((b & 0x0f) << 4 | (b & 0xf0) >> 4)
                
            yield bytes(newdata).hex() + '\n'

    # TODO: nicer accessors
