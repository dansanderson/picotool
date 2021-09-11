"""Loading and saving PICO-8 carts in various file formats"""

__all__ = [
    'formatter_for_filename',
    'UnrecognizedFileType',
]

import collections
import os
import tempfile

from .. import util

from formatter.p8 import P8Formatter
from formatter.p8png import P8PNGFormatter
from formatter.rom import ROMFormatter


Formatter = collections.namedtuple('Formatter', ('extension', 'cls'))
FORMATTERS = (
    Formatter('.p8.png', P8PNGFormatter),
    Formatter('.p8', P8Formatter),
    Formatter('.rom', ROMFormatter),
)


class UnrecognizedFileType(util.InvalidP8DataError):
    """Exception for unrecognized file type."""
    def __init__(self, filename):
        self.filename = filename
        super().__init__(f'Filename {filename} is not of a supported type')


def formatter_for_filename(filename):
    """Determines the formatter for a given filename.

    Args:
        filename: The filename.

    Returns:
        A BaseFormatter subclass.

    Raises:
        UnrecognizedFileType
    """
    for fmt in FORMATTERS:
        if filename.endswith(fmt.extension):
            return fmt.cls
    raise UnrecognizedFileType(filename)


def from_file(cls, filename):
    """Loads a game from a named file.

    Args:
        filename: The name of the file. Must end in either ".p8" or
        ".p8.png".

    Returns:
        A Game containing the game data.

    Raises:
        lexer.LexerError
        parser.ParserError
        InvalidP8HeaderError
    """
    fmt = formatter_for_filename(filename=filename)
    with open(filename, 'rb') as fh:
        return fmt.from_file(fh, filename=filename)


def to_file(self, filename, *args, **kwargs):
    """Write the game data to a file, based on a filename.

    If filename ends with .p8.png, the output is a .p8.png file. If the
    output file exists, its label is reused, otherwise an empty label is
    used. The label can be overridden by the caller with the
    'label_fname' argument.

    Args:
        filename: The filename.
    """
    fmt = formatter_for_filename(filename)
    file_args = {'mode': 'wb+'}
    with tempfile.TemporaryFile(**file_args) as outfh:
        if kwargs.get('label_fname', None) is None:
            if os.path.exists(filename):
                kwargs['label_fname'] = filename
        fmt.to_file(self, outfh, filename=filename, *args, **kwargs)
        outfh.seek(0)
        with open(filename, **file_args) as finalfh:
            finalfh.write(outfh.read())
