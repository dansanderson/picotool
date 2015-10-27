"""The graphics flags section of a Pico-8 cart.

The graphics properties region consists of 256 bytes. The .p8
representation is 2 lines of 256 hexadecimal digits (128 bytes).

This represents eight flags for each of the 128 tiles in the main gfx
area. In the graphics editor, the flags are arranged left to right
from LSB to MSB: red=1, orange=2, yellow=4, green=8, blue=16, purple=32,
pink=64, peach=128.

"""
# TODO: more documentaion

__all__ = ['Gff']

from .. import util


class Gff(util.BaseSection):
    """The graphics properties section of a Pico-8 cart."""
    HEX_LINE_LENGTH_BYTES = 128
    
    # TODO: nicer accessors
