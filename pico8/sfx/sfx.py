"""The sound effects section of a Pico-8 cart.

The sound effects region consists of 4352 bytes. The .p8
representation is 64 lines of 168 hexadecimal digits (84 bytes).

Each line represents one sound effect/music pattern. The values are as follows:
 0    The editor mode: 0 for pitch mode, 1 for note entry mode.
 1    The note duration, in multiples of 1/128 second.
 2    Loop range start, as a note number (0-63).
 3    Loop range end, as a note number (0-63).
4-84  32 notes:
        0: pitch (0-63): c-0 to d#-5, chromatic scale
        1-high: waveform (0-7):
          0 sine, 1 triangle, 2 sawtooth, 3 long square, 4 short square,
          5 ringing, 6 noise, 7 ringing sine
        1-low: volume (0-7)
        2-high: effect (0-7):
          0 none, 1 slide, 2 vibrato, 3 drop, 4 fade_in, 5 fade_out,
          6 arp fast, 7 arp slow; arpeggio commands loop over groups of
          four notes at speed 2 (fast) and 4 (slow)
      One note uses five nibbles, so two notes use five bytes.

The RAM representation is different. Each pattern is 68 bytes, with
two bytes for each of 32 notes, one byte for the editor mode, one byte
for the speed, and two bytes for the loop range (start, end). Each
note is encoded in 16 bits, LSB first, like so:

  w2-w1-pppppp ?-eee-vvv-w3

  eee: effect (0-7)
  vvv: volume (0-7)
  w3w2w1: waveform (0-7)
  pppppp: pitch (0-63) 

The highest bit appears to be unused, but Pico-8 sets it for the 2nd
note in the pattern for some reason.
"""

__all__ = ['Sfx']

from .. import util

class Sfx(util.BaseSection):
    """The sfx region of a Pico-8 cart."""

    HEX_LINE_LENGTH_BYTES = 84

    @classmethod
    def from_lines(cls, lines, version):
        """Create an instance based on .p8 data lines.

        Args:
          lines: .p8 lines for the section.
          version: The Pico-8 data version from the game file header.
        """
        data = bytearray()

        for l in lines:
            if len(l) != 168:
                continue
            editor_mode = bytes.fromhex(l[0:2])
            note_duration = bytes.fromhex(l[2:4])
            loop_start = bytes.fromhex(l[4:6])
            loop_end = bytes.fromhex(l[6:8])
            for i in range(8,168,5):
                pitch = bytes.fromhex(l[i:i+1])
                waveform = bytes.fromhex(l[i+2])
                volume = bytes.fromhex(l[i+3])
                effect = bytes.fromhex(l[i+4])

                lsb = pitch | ((waveform & 3) << 6)
                data.append(lsb)
                msb = effect << 4 | volume << 1 | (waveform & 4 >> 2)
                if i == 10:
                    # Follow Pico-8's lead and set the most significant bit of
                    # the 2nd note in the pattern.
                    msb |= 128
                data.append(msb)
            data.append(editor_mode)
            data.append(note_duration)
            data.append(loop_start)
            data.append(loop_end)

        return cls(data=data, version=version)

    def to_lines(self):
        """Generates lines of ASCII-encoded hexadecimal strings.

        Yields:
          One line of a hex string.
        """
        for i in range(0, len(self._data), 68):
            hexstrs = []
            
            editor_mode = self._data[i+64]
            note_duration = self._data[i+65]
            loop_start = self._data[i+66]
            loop_end = self._data[i+67]
            hexstrs.append(bytes([editor_mode, note_duration,
                                  loop_start, loop_end]).hex())

            for ni in range(0, 64, 2):
                lsb = self._data[i+ni]
                msb = self._data[i+ni+1]
                pitch = lsb & 63
                waveform = msb & 1 << 2 | (lsb & 192) >> 6
                volume = msb & 14 >> 1
                effect = msb & 112 >> 4

                hexstrs.append(bytes([pitch, waveform << 4 | volume]).hex())
                hexstrs.append(bytes([effect]).hex()[1])

            yield ''.join(hexstrs) + '\n'
        
    # TODO: nicer accessors
