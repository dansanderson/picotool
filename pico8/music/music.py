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
    def empty(cls, version):
        """Creates an empty instance.

        Args:
          version: The Pico-8 file version.

        Returns:
          A Music instance.
        """
        return cls(data=bytearray(b'\x41\x42\x43\x44' * 64), version=version)
    
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
            if l.find(b' ') == -1:
                continue
            flagstr, chanstr = l.split(b' ')
            flags = bytes.fromhex(str(flagstr, encoding='ascii'))[0]
            fstop = (flags & 4) >> 2
            frepeat = (flags & 2) >> 1
            fnext = flags & 1

            chan1 = bytes.fromhex(str(chanstr[0:2], encoding='ascii'))
            chan2 = bytes.fromhex(str(chanstr[2:4], encoding='ascii'))
            chan3 = bytes.fromhex(str(chanstr[4:6], encoding='ascii'))
            chan4 = bytes.fromhex(str(chanstr[6:8], encoding='ascii'))
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
            yield (bytes(bytes([p8flags]).hex(), encoding='ascii') + b' ' +
                   bytes(bytes([chan1, chan2, chan3, chan4]).hex(), encoding='ascii') + b'\n')

    def get_channel(self, id, channel):
        """Gets the sfx ID on a channel for a given pattern.

        Args:
          id: The music ID. (0-63)
          channel: The channel. (0-3)

        Returns:
          The sfx ID on the channel, or None if the channel is silent.
        """
        assert 0 <= id <= 63
        assert 0 <= channel <= 3
        pattern = self._data[id * 4 + channel] & 0x7f
        if pattern > 63:
            return None
        return pattern
    
    def set_channel(self, id, channel, pattern):
        """Sets the sfx ID on a channel of a pattern.

        Args:
          id: The music ID. (0-63)
          channel: The channel. (0-3)
          pattern: The sfx ID, or None to set the channel to silent.
        """
        assert 0 <= id <= 63
        assert 0 <= channel <= 3
        assert (pattern is None) or (0 <= pattern <= 63)
        if pattern is None:
            pattern = 0x40 + channel + 1
        self._data[id * 4 + channel] = ((self._data[id * 4 + channel] & 0x80) |
                                        pattern)
        
    def get_properties(self, id):
        """Gets the properties of the music pattern.

        begin is True if the music pattern is the beginning of a looping region.

        end is True if the music pattern is the end of a looping region.

        stop is True if the music stops after this pattern is played.

        Args:
          id: The music ID. (0-63)

        Returns:
          A tuple: (being, end, stop). These are Booleans (True or False).
        """
        assert 0 <= id <= 63
        begin = (self._data[id * 4] & 0x80) > 0
        end = (self._data[id * 4 + 1] & 0x80) > 0
        stop = (self._data[id * 4 + 2] & 0x80) > 0
        return (begin, end, stop)
    
    def set_properties(self, id, begin=None, end=None, stop=None):
        """Sets the properties of the music pattern.

        Specify values of True or False to change a property, or None to leave
        the property unchanged.

        Args:
          id: The music ID. (0-63)
          begin: True to set the flag, False to unset the flag, or None to
            leave it unchanged.
          end: True to set the flag, False to unset the flag, or None to
            leave it unchanged.
          stop: True to set the flag, False to unset the flag, or None to
            leave it unchanged.
        """
        if begin is not None:
            self._data[id * 4] = ((self._data[id * 4] & 0x7f) |
                                  (0x80 if begin else 0x00))
        if end is not None:
            self._data[id * 4 + 1] = ((self._data[id * 4 + 1] & 0x7f) |
                                      (0x80 if end else 0x00))
        if stop is not None:
            self._data[id * 4 + 2] = ((self._data[id * 4 + 2] & 0x7f) |
                                      (0x80 if stop else 0x00))
