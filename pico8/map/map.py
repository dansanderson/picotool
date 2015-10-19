"""The map section of a Pico-8 cart.

The map region consists of 4096 bytes. The .p8 representation is 32
lines of 256 hexadecimal digits (128 bytes).
"""
# TODO: more documentaion

__all__ = ['Map']

from .. import util

class Map(util.BaseSection):
    """The map region of a Pico-8 cart."""
    # TODO: nicer accessors
    pass
