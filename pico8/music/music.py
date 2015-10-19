"""The music (song) region of a Pico-8 cart.

The music region consists of 256 bytes. The .p8 representation is one
line for each of 64 patterns, with a hex-encoded flags byte, a space,
and four hex-encoded one-byte sound numbers.

The flags are:
 1: begin pattern loop
 2: end pattern loop
 4: stop at end of pattern

The sound numbers represents four channels played simultaneously up to
the shortest pattern. The sounds are numbered 0 through 63
(0x00-0x3f). If a channel is silent for a song pattern, its number is
64 + the channel number (0x41, 0x42, 0x43, or 0x44).
"""

__all__ = ['Music']

from .. import util

class Music(util.BaseSection):
    @classmethod
    def from_lines(cls, lines, version):
        """
        Args:
          lines: .p8 lines for the music section.
          version: The Pico-8 data version from the game file header.
        """
        bytestrs = []
        for l in lines:
            bytestrs.extend(l.rstrip().split(' '))
        data = b''.join(bytearray.fromhex(p)
                        for p in bytestrs)
        return cls(data=data, version=version)
