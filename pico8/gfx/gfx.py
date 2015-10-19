"""The sprite graphics section of a Pico-8 cart.

The graphics region consists of 8192 bytes. The .p8 representation is
128 lines of 128 hexadecimal digits (64 bytes).
"""
# TODO: more documentaion

__all__ = ['Gfx']

from .. import util

class Gfx(util.BaseSection):
    """The sprite graphics section for a Pico-8 cart."""
    # TODO: nicer accessors
    pass
