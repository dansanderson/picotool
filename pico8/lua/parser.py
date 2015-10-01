"""The Lua parser."""

from .. import util
from . import lexer


__all__ = [
    'ParserError',
]


class ParserError(util.InvalidP8DataError):
    """A lexer error."""
    def __init__(self, msg, lineno, charno):
        self.msg = msg
        self.lineno = lineno
        self.charno = charno
        
    def __str__(self):
        return '{} at line {} char {}'.format(
            self.msg, self.lineno, self.charno)


class Node():
    """A base class for all AST nodes."""
    pass
