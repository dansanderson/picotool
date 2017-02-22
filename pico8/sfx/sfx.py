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

The highest bit appears to be unused. In RAM, Pico-8 sets it for the 2nd
note in the pattern for some reason, but this is not written to the PNG.
"""

__all__ = ['Sfx']

from .. import util


WAVEFORM_SINE = 0
WAVEFORM_TRIANGLE = 1
WAVEFORM_SAWTOOTH = 2
WAVEFORM_LONG_SQUARE = 3
WAVEFORM_SHORT_SQUARE = 4
WAVEFORM_RINGING = 5
WAVEFORM_NOISE = 6
WAVEFORM_RINGING_SINE = 7
EFFECT_NONE = 0 
EFFECT_SLIDE = 1
EFFECT_VIBRATO = 2 
EFFECT_DROP = 3
EFFECT_FADE_IN = 4
EFFECT_FADE_OUT = 5
EFFECT_ARP_FAST = 6
EFFECT_ARP_SLOW = 7


class Sfx(util.BaseSection):
    """The sfx region of a Pico-8 cart."""

    HEX_LINE_LENGTH_BYTES = 84

    @classmethod
    def empty(cls, version):
        """Creates an empty instance.

        Args:
          version: The Pico-8 file version.

        Returns:
          A Sfx instance.
        """
        result = cls(data=bytearray(b'\x00' * 4352), version=version)
        
        # Emulate Pico-8 defaults:
        result.set_properties(0, note_duration=1)
        for i in range(1,64):
            result.set_properties(i, note_duration=16)
            
        return result
    
    @classmethod
    def from_lines(cls, lines, version):
        """Create an instance based on .p8 data lines.

        Args:
          lines: .p8 lines for the section.
          version: The Pico-8 data version from the game file header.
        """
        result = cls.empty(version=version)
        id = 0
        
        for l in lines:
            if len(l) != 169:
                continue
            editor_mode = int(l[0:2], 16)
            note_duration = int(l[2:4], 16)
            loop_start = int(l[4:6], 16)
            loop_end = int(l[6:8], 16)
            result.set_properties(id,
                                  editor_mode=editor_mode,
                                  note_duration=note_duration,
                                  loop_start=loop_start,
                                  loop_end=loop_end)
            note = 0
            for i in range(8,168,5):
                pitch = int(l[i:i+2], 16)
                waveform = int(l[i+2:i+3], 16)
                volume = int(l[i+3:i+4], 16)
                effect = int(l[i+4:i+5], 16)
                result.set_note(id, note,
                                pitch=pitch,
                                waveform=waveform,
                                volume=volume,
                                effect=effect)
                note += 1
            id += 1

        return result

    def to_lines(self):
        """Generates lines of ASCII-encoded hexadecimal strings.

        Yields:
          One line of a hex string.
        """
        for id in range(0, 64):
            hexstrs = [bytes(bytes(self.get_properties(id)).hex(), encoding='ascii')]
            for note in range(0, 32):
                pitch, waveform, volume, effect = self.get_note(id, note)
                hexstrs.append(bytes(bytes([pitch, waveform << 4 | volume]).hex(), encoding='ascii'))
                hexstrs.append(bytes(bytes([effect]).hex()[1], encoding='ascii'))
            yield b''.join(hexstrs) + b'\n'

    def get_note(self, id, note):
        """Gets a note from a pattern.

        pitch is a value (0-63), representing the notes on a chromatic scale
        from c-0 to d#-5.

        waveform is one fo the WAVEFORM_* constants (0-7).

        volume is 0-7: 0 is off, 7 is loudest.

        effect is one of the EFFECT_* constants (0-7).

        Args:
          id: The pattern ID. (0-63)
          note: The note number. (0-31)

        Returns:
          A tuple: (pitch, waveform, volume, effect).
        """
        lsb = self._data[id * 68 + note * 2]
        msb = self._data[id * 68 + note * 2 + 1]
        pitch = lsb & 0x3f
        waveform = ((msb & 0x01) << 2) | ((lsb & 0xc0) >> 6)
        volume = (msb & 0x0e) >> 1
        effect = (msb & 0x70) >> 4
        return (pitch, waveform, volume, effect)

    def set_note(self, id, note, pitch=None, waveform=None, volume=None,
                 effect=None):
        """Sets a note in a pattern.

        (See get_note() for definitions.)

        Args:
          id: The pattern ID. (0-63)
          note: The note number. (0-31)
          pitch: The pitch value, or None to leave unchanged. (0-63)
          waveform: The waveform type, or None to leave unchanged. (0-7)
          volume: The volume level, or None to leave unchanged. (0-7)
          effect: The effect type, or None to leave unchanged. (0-7)
        """
        lsb = self._data[id * 68 + note * 2]
        msb = self._data[id * 68 + note * 2 + 1]

        if pitch is not None:
            assert 0 <= pitch <= 63
            lsb = (lsb & 0xc0) | pitch
        if waveform is not None:
            assert 0 <= waveform <= 7
            lsb = (lsb & 0x3f) | ((waveform & 3) << 6)
            msb = (msb & 0xfe) | ((waveform & 4) >> 2) 
        if volume is not None:
            assert 0 <= volume <= 7
            msb = (msb & 0xf1) | (volume << 1)
        if effect is not None:
            assert 0 <= effect <= 7
            msb = (msb & 0x8f) | (effect << 4)
        
        self._data[id * 68 + note * 2] = lsb
        self._data[id * 68 + note * 2 + 1] = msb
        
    def get_properties(self, id):
        """Gets properties for a pattern.

        editor_mode is 0 for pitch mode, 1 for note mode.

        note_duration is the duration of each note, in 1/128ths of a second.
        (0-255)

        loop_start is the loop range start, as a note number. (0-63)

        loop_end is the loop range end, as a note number. (0-63)

        Args:
          id: The pattern ID. (0-63)

        Returns:
          A tuple: (editor_mode, note_duration, loop_start, loop_end).
        """
        return (self._data[id * 68 + 64],
                self._data[id * 68 + 65],
                self._data[id * 68 + 66],
                self._data[id * 68 + 67])

    def set_properties(self, id, editor_mode=None, note_duration=None,
                       loop_start=None, loop_end=None):
        """Sets properteis for a pattern.

        Args:
          id: The pattern ID. (0-63)
          editor_mode: 0 for pitch mode, 1 for note mode, None to leave
            unchanged.
          note_duration: The duration for each note in the pattern, in 1/128ths
            of a second. (0-255) None to leave unchanged.
          loop_start: The loop range start, as a note number (0-63). None to
            leave unchanged.
          loop_end: The loop range end, as a note number (0-63). None to
            leave unchanged.
        """
        # (The asserts are only appropriate if the cart uses the sfx memory
        # for actual sfx, which not all carts do. Keeping them for
        # documentation purposes.)
        if editor_mode is not None:
            # assert 0 <= editor_mode <= 1
            self._data[id * 68 + 64] = editor_mode
        if note_duration is not None:
            # assert 0 <= note_duration <= 255
            self._data[id * 68 + 65] = note_duration
        if loop_start is not None:
            # assert 0 <= loop_start <= 63
            self._data[id * 68 + 66] = loop_start
        if loop_end is not None:
            # assert 0 <= loop_end <= 63
            self._data[id * 68 + 67] = loop_end
