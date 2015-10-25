"""The sprite graphics section of a Pico-8 cart.

The graphics region consists of 8192 bytes. The .p8 representation is
128 lines of 128 hexadecimal digits (64 bytes).

The in-memory representation is similar, but with nibble-pairs
swapped. (The .p8 representation resembles pixel left-to-right
ordering, while the RAM representation uses the most significant
nibble for the right pixel of each pixel pair.)
"""
# TODO: more documentaion

__all__ = ['Gfx']

from .. import util

class Gfx(util.BaseSection):
    """The sprite graphics section for a Pico-8 cart."""
    HEX_LINE_LENGTH_BYTES = 64

    @classmethod
    def from_lines(cls, lines, version):
        """Create an instance based on .p8 data lines.

        The base implementation reads lines of ASCII-encoded hexadecimal bytes.

        Args:
          lines: .p8 lines for the section.
          version: The Pico-8 data version from the game file header.
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
            if end_i > len(self._data):
                end_i = len(self._data)

            newdata = []
            for b in self._data[start_i:end_i]:
                newdata.append((b & 0x0f) << 4 | (b & 0xf0) >> 4)
                
            yield bytes(newdata).hex() + '\n'

    # TODO: nicer accessors
