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

The in-memory (and PNG) representation is slightly different from the
.p8 representation. Instead of storing the flags in a separate byte,
the flags are stored in the highest bit of the first three channels,
for a total of four bytes:
 chan1 & 128: stop at end of pattern
 chan2 & 128: end pattern loop
 chan3 & 128: begin pattern loop
"""

__all__ = ['Music']

from .. import util


class Music(util.BaseSection):
    @classmethod
    def from_lines(cls, lines, version):
        """Parse the music .p8 section into memory bytes.

        Args:
          lines: .p8 lines for the music section.
          version: The Pico-8 data version from the game file header.

        Returns:
          A Music instance with the loaded data.
        """
        data = bytearray()
        for l in lines:
            if l.find(' ') == -1:
                continue
            flagstr, chanstr = l.split(' ')
            flags = bytes.fromhex(flagstr)[0]
            fstop = (flags & 4) >> 2
            frepeat = (flags & 2) >> 1
            fnext = flags & 1

            chan1 = bytes.fromhex(chanstr[0:2])
            chan2 = bytes.fromhex(chanstr[2:4])
            chan3 = bytes.fromhex(chanstr[4:6])
            chan4 = bytes.fromhex(chanstr[6:8])
            data.append(chan1[0] | fnext << 7)
            data.append(chan2[0] | frepeat << 7)
            data.append(chan3[0] | fstop << 7)
            data.append(chan4[0])
        
        return cls(data=data, version=version)

    def to_lines(self):
        """Generates lines for the music section of a .p8 file.

        Yields:
          One line.
        """
        for start_i in range(0, len(self._data), 4):
            fstop = (self._data[start_i+2] & 128) >> 7
            frepeat = (self._data[start_i+1] & 128) >> 7
            fnext = (self._data[start_i] & 128) >> 7
            p8flags = (fstop << 2) | (frepeat << 1) | fnext
            chan1 = self._data[start_i] & 127
            chan2 = self._data[start_i+1] & 127
            chan3 = self._data[start_i+2] & 127
            chan4 = self._data[start_i+3] & 127
            yield (bytes([p8flags]).hex() + ' ' +
                   bytes([chan1, chan2, chan3, chan4]).hex() + '\n')
