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
"""

__all__ = ['Sfx']

from .. import util

class Sfx(util.BaseSection):
    """The sfx region of a Pico-8 cart."""
    # TODO: nicer accessors
    pass
