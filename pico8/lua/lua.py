"""The Lua code for a game."""

__all__ = ['Lua']

from . import lexer
from . import parser


class Lua():
    """The Lua code for a game."""
    def __init__(self, version):
        """Initializer.

        If loading from a file, prefer Lua.from_lines().

        Args:
          version: The Pico-8 data version from the game file header.
        """
        self._version = version
        self._lexer = lexer.Lexer(version=version)
        self._parser = parser.Parser(version=version)

    def get_char_count(self):
        return sum(len(t) for t in self._lexer._tokens)

    @classmethod
    def from_lines(cls, lines, version):
        """Produce a Lua data object from lines of Lua source.

        Args:
          lines: The Lua source, as an iterable of strings.
          version: The Pico-8 data version from the game file header.

        Returns:
          A populated Lua instance.
        """
        result = Lua(version)
        result._lexer.process_lines(lines)
        result._parser.process_tokens(result._lexer.tokens)
        return result
