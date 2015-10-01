"""Utility classes and functions for the picotool tools and libraries."""

import sys

__all__ = [
    'Error',
    'InvalidP8DataError',
    'set_quiet',
    'write',
    'error'
]


_quiet = False
_write_stream = sys.stdout
_error_stream = sys.stderr


class Error(Exception):
    """A base class for all errors in the picotool libraries."""
    pass


class InvalidP8DataError(Error):
    """A base class for all invalid game file errors."""
    pass


def set_quiet(new_quiet=False):
    global _quiet
    _quiet = new_quiet

    
def write(msg):
    """Writes a message to the user.

    Messages written with this function can be suppressed by the user
    with the --quiet argument.

    When working with named files, this function writes to
    stdout. When working with stdin, file output goes to stdout and
    messages go to stderr.

    Args:
      msg: The message to write.

    """
    if not _quiet:
        _write_stream.write(msg)


def error(msg):
    """Writes an error message to the user.

    All error messages are written to stderr.

    Args:
      msg: The error message to write.
    """
    _error_stream.write(msg)
