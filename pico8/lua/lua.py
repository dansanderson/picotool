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

    def get_token_count(self):
        c = 0
        for t in self._lexer._tokens:
            if (not isinstance(t, lexer.TokSpace) and
                not isinstance(t, lexer.TokNewline) and
                not isinstance(t, lexer.TokComment)):
                c += 1
        return c

    def get_line_count(self):
        c = 0
        for t in self._lexer._tokens:
            if isinstance(t, lexer.TokNewline):
                c += 1
        return c

    def get_title(self):
        if len(self._lexer.tokens) < 1:
            return None
        title_tok = self._lexer.tokens[0]
        if not isinstance(title_tok, lexer.TokComment):
            return None
        return title_tok.value[2:].strip()

    def get_byline(self):
        if len(self._lexer.tokens) < 3:
            return None
        title_tok = self._lexer.tokens[2]
        if not isinstance(title_tok, lexer.TokComment):
            return None
        return title_tok.value[2:].strip()

    @property
    def tokens(self):
        return self._lexer.tokens

    @property
    def root(self):
        return self._parser.root

    @property
    def version(self):
        return self._version

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

    def to_lines(self, writer_cls=None):
        """Generates lines of Lua source based on the parser output.

        Args:
          writer_cls: The writer class to use. If None, defaults to
            LuaEchoWriter.

        Yields:
          A line of Lua code.
        """
        if writer_cls is None:
            writer_cls = LuaEchoWriter
        writer = writer_cls(tokens=self._lexer.tokens, root=self._parser.root)
        for line in writer.to_lines():
            yield line


class BaseLuaWriter():
    """A base class for Lua writers."""
    def __init__(self, tokens, root):
        """Initializer.

        Args:
          tokens: The lexer tokens.
          root: The root of the AST produced by the parser.
        """
        self._tokens = tokens
        self._root = root
        
    def to_lines(self):
        """Generates lines of Lua source based on the parser output.

        Yields:
          A line of Lua code.
        """
        raise NotImplementedError


class LuaEchoWriter(BaseLuaWriter):
    """Writes the Lua code to be identical to the input given to the parser.

    This ignores the parser and just writes out the string values of the
    original token stream.
    """
    def to_lines(self):
        strs = []
        for token in self._tokens:
            strs.append(token.value)
            if token.matches(lexer.TokNewline):
                yield ''.join(strs)
                strs.clear()
        if strs:
            yield ''.join(strs)
