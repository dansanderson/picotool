"""The graphics properties section of a Pico-8 cart.

The graphics properties region consists of 256 bytes. The .p8
representation is 2 lines of 256 hexadecimal digits (128 bytes).
"""
# TODO: more documentaion

__all__ = ['Gff']

from .. import util

class Gff(util.BaseSection):
    """The graphics properties section of a Pico-8 cart."""
    HEX_LINE_LENGTH_BYTES = 128
    
    # TODO: nicer accessors
