"""Utility classes and functions for the picotool tools and libraries."""

import sys

__all__ = [
    'Error',
    'InvalidP8DataError',
    'set_quiet',
    'write',
    'error'
]


VERBOSITY_QUIET = 1    # error
VERBOSITY_NORMAL = 2   # write and error
VERBOSITY_DEBUG = 3    # debug, write and error
_verbosity = VERBOSITY_NORMAL

_write_stream = sys.stdout
_error_stream = sys.stderr
    

class Error(Exception):
    """A base class for all errors in the picotool libraries."""
    pass


class InvalidP8DataError(Error):
    """A base class for all invalid game file errors."""
    pass


def set_verbosity(level=VERBOSITY_NORMAL):
    global _verbosity
    _verbosity = level


def debug(msg):
    """Writes a debug message.

    This does nothing unless the user specifies the --debug argument.

    When working with named files, this function writes to
    stdout. When working with stdin, file output goes to stdout and
    messages go to stderr.

    Args:
      msg: The message to write.
    """
    if _verbosity >= VERBOSITY_DEBUG:
        _write_stream.write(msg)

        
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
    if _verbosity >= VERBOSITY_NORMAL:
        _write_stream.write(msg)


def error(msg):
    """Writes an error message to the user.

    All error messages are written to stderr.

    Args:
      msg: The error message to write.
    """
    _error_stream.write(msg)


class BaseSection():
    """A base class for Pico-8 section objects."""

    def __init__(self, data, version):
        """Initializer.

        If loading from a file, prefer from_lines() or from_bytes().

        Args:
          version: The Pico-8 data version from the game file header.
          data: The data region, as a sequence of bytes.
        """
        self._version = version
        self._data = bytearray(data)

    @classmethod
    def from_lines(cls, lines, version):
        """Create an instance based on .p8 data lines.

        The base implementation reads lines of ASCII-encoded hexadecimal bytes.

        Args:
          lines: .p8 lines for the section.
          version: The Pico-8 data version from the game file header.
        """
        data = b''.join(bytearray.fromhex(l.rstrip()) for l in lines)
        return cls(data=data, version=version)

    HEX_LINE_LENGTH_BYTES = 64
    def to_lines(self):
        """Generates lines of ASCII-encoded hexadecimal strings.

        Yields:
          One line of a hex string.
        """
        for start_i in range(0, len(self._data), self.HEX_LINE_LENGTH_BYTES):
            end_i = start_i + self.HEX_LINE_LENGTH_BYTES
            if end_i > len(self._data):
                end_i = len(self._data)
            yield bytes(self._data[start_i:end_i]).hex() + '\n'
    
    @classmethod
    def from_bytes(cls, data, version):
        """
        Args:
          data: Binary data for the section, as a sequence of bytes.
          version: The Pico-8 data version from the game file header.
        """
        return cls(data=data, version=version)
