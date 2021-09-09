"""The Lua lexer."""

import re

from .. import util


__all__ = [
    'LexerError',
    'Token',
    'TokSpace',
    'TokNewline',
    'TokComment',
    'TokString',
    'TokNumber',
    'TokName',
    'TokLabel',
    'TokKeyword',
    'TokSymbol',
    'Lexer',
    'LUA_KEYWORDS'
]

LUA_KEYWORDS = {
    b'and', b'break', b'do', b'else', b'elseif', b'end', b'false', b'for',
    b'function', b'goto', b'if', b'in', b'local', b'nil', b'not', b'or',
    b'repeat', b'return', b'then', b'true', b'until', b'while'
}


class LexerError(util.InvalidP8DataError):
    """A lexer error."""

    def __init__(self, msg, lineno, charno):
        self.msg = msg
        self.lineno = lineno
        self.charno = charno

    def __str__(self):
        return '{} at line {} char {}'.format(
            self.msg, self.lineno, self.charno)


class Token():
    """A base class for all tokens."""

    def __init__(self, data, lineno=None, charno=None):
        """Initializer.

        Args:
          data: The code data for the token.
          lineno: The source file line number of the first character.
          charno: The character number on the line of the first character.
        """
        self._data = data
        self._lineno = lineno
        self._charno = charno

    def __len__(self):
        """The length of the code string for the token."""
        return len(self.code)

    def __repr__(self):
        """A textual representation for debugging."""
        return '{}<{}, line {} char {}>'.format(
            self.__class__.__name__, repr(self._data),
            self._lineno, self._charno)

    def __eq__(self, other):
        """Equality operator.

        Two tokens are equal if they are of the same type and have
        equal data. Positions are insignificant.

        Args:
          other: The other Token to compare.
        """
        if (type(self) != type(other) or
                not isinstance(self, other.__class__)):
            return False
        if (isinstance(self, TokKeyword) and
                isinstance(other, TokKeyword)):
            return self._data.lower() == other._data.lower()
        return self._data == other._data

    def matches(self, other):
        """Matches the token against either a token class or token data.

        This is shorthand for the parser, which either wants to know
        whether the token is of a particular kind (e.g. a TokName) or
        of a particular value (a specific TokSymbol or TokKeyword).

        Args:
          other: The other Token to compare.
        """
        if isinstance(other, type):
            return isinstance(self, other)

        return self == other

    @property
    def value(self):
        """The parsed value of the token."""
        return self._data

    @property
    def code(self):
        """The original code of the token."""
        return self._data

    @code.setter
    def code(self, value):
        """Setter for code.

        Use this wisely! This does not validate that your updated token
        matches the token type.
        """
        self._data = value


class TokSpace(Token):
    """A block of whitespace, not including newlines."""
    name = 'whitespace'


class TokNewline(Token):
    """A single newline."""
    name = 'newline'


class TokComment(Token):
    """A Lua comment, including the '--' characters."""
    name = 'comment'


class TokString(Token):
    """A string literal."""
    name = 'string literal'

    def __init__(self, *args, **kwargs):
        self._quote = None
        self._multiline_quote = None

        if 'multiline_quote' in kwargs:
            self._multiline_quote = kwargs['multiline_quote']
            del kwargs['multiline_quote']
        elif 'quote' in kwargs:
            self._quote = kwargs['quote']
            del kwargs['quote']
        else:
            self._quote = b'"'
        super().__init__(*args, **kwargs)

    @property
    def code(self):
        if self._multiline_quote is not None:
            return (b'[' + self._multiline_quote + b'[' +
                    self._data +
                    b']' + self._multiline_quote + b']')
        else:
            escaped_chrs = []
            for c in self._data:
                c = bytes([c])
                if c in _STRING_REVERSE_ESCAPES:
                    escaped_chrs.append(b'\\' + _STRING_REVERSE_ESCAPES[c])
                elif c == self._quote:
                    escaped_chrs.append(b'\\' + c)
                else:
                    escaped_chrs.append(c)
            return self._quote + b''.join(escaped_chrs) + self._quote

    @code.setter
    def code(self, value):
        """Setter for code.

        Use this wisely! This does not validate that your updated token
        matches the token type.
        """
        self._data = value


class TokNumber(Token):
    """A number literal.

    Negative number literals are tokenized as two tokens: a
    TokSymbol('-'), and a TokNumber(...) representing the non-negative
    number part.

    The value() method converts the number to a Python number. Keep in mind
    that Python numbers are not fixed point as PICO-8's are, so the result
    may not exactly match PICO-8.
    """
    name = 'number'

    # self._data is the original string representation of the number,
    # so we don't have to jump through hoops to recreate it later.
    @property
    def value(self):
        if b'x' in self._data:
            if b'.' in self._data:
                integer, frac = self._data.split(b'.')
                return (
                    float(int(integer, 16)) +
                    float(int(frac, 16))/(16**len(frac)))
            return float(int(self._data, 16))
        if b'b' in self._data:
            if b'.' in self._data:
                integer, frac = self._data.split(b'.')
                return (
                    float(int(integer, 2)) +
                    float(int(frac, 2))/(2**len(frac)))
            return float(int(self._data, 2))
        return float(self._data)


class TokName(Token):
    """A variable or function name."""
    name = 'name'


class TokLabel(Token):
    """A goto label."""
    name = 'label'


class TokKeyword(Token):
    """A Lua keyword."""
    name = 'keyword'


class TokSymbol(Token):
    """A Lua symbol."""
    name = 'symbol'


# A mapping of characters that can be escaped in Lua string literals using a
# "\" character, mapped to their unescaped values.
_STRING_ESCAPES = {
    b'\n': b'\n', b'a': b'\a', b'b': b'\b', b'f': b'\f', b'n': b'\n',
    b'r': b'\r', b't': b'\t', b'v': b'\v', b'\\': b'\\', b'"': b'"',
    b"'": b"'"
}
_STRING_REVERSE_ESCAPES = dict((v, k) for k, v in _STRING_ESCAPES.items())
del _STRING_REVERSE_ESCAPES[b"'"]
del _STRING_REVERSE_ESCAPES[b'"']

# A list of single-line token matching patterns and corresponding token
# classes. A token class of None causes the lexer to consume the pattern
# without emitting a token. The patterns are matched in order.
_TOKEN_MATCHERS = []
_TOKEN_MATCHERS.extend([
    (re.compile(br'--.*'), TokComment),
    (re.compile(br'//.*'), TokComment),
    (re.compile(br'[ \t]+'), TokSpace),
    (re.compile(br'\r\n'), TokNewline),
    (re.compile(br'\n'), TokNewline),
    (re.compile(br'\r'), TokNewline),
    (re.compile(br'0[xX][0-9a-fA-F]+(\.[0-9a-fA-F]+)?'), TokNumber),
    (re.compile(br'0[xX]\.[0-9a-fA-F]+'), TokNumber),
    (re.compile(br'0[bB][01]+(\.[01]+)?'), TokNumber),
    (re.compile(br'0[bB]\.[01]+'), TokNumber),
    (re.compile(br'[0-9]+(\.(?!\.)[0-9]*)?([eE]-?[0-9]+)?'), TokNumber),
    (re.compile(br'\.[0-9]+([eE]-?[0-9]+)?'), TokNumber),
    (re.compile(br'::[a-zA-Z_][a-zA-Z0-9_]*::'), TokLabel),
])
_TOKEN_MATCHERS.extend([
    (re.compile(br'\b'+keyword+br'\b'), TokKeyword)
    for keyword in LUA_KEYWORDS])
# REMINDER: token patterns are ordered! The lexer stops at the first matching
# pattern. This is especially tricky for the symbols because you have to make
# sure symbols like >>> appear before >>. (If >> appeared first in this list,
# >>> would never match.)
_TOKEN_MATCHERS.extend([
    (re.compile(symbol), TokSymbol) for symbol in [
        br'\+=', b'-=', br'\*=', b'/=', b'%=', br'\.\.=',
        b'==', b'~=', b'!=', b'<=', b'>=',
        b'&', br'\|', br'\^\^', b'~', b'<<>', b'>>>', b'>><', b'<<', b'>>',
        br'\\',
        br'\+', b'-', br'\*', b'/', b'%', br'\^', b'#',
        b'@', br'\$',
        b'<', b'>', b'=',
        br'\(', br'\)', b'{', b'}', br'\[', br'\]', b';', b':', b',',
        br'\.\.\.', br'\.\.', br'\.']])
_TOKEN_MATCHERS.extend([
    (re.compile(br'[a-zA-Z_][a-zA-Z0-9_]*'), TokName),
    (re.compile(br'\?'), TokName)
])


class Lexer():
    """The lexer.

    A lexer object maintains state between calls to process_line() to
    manage tokens that span multiple lines.
    """

    def __init__(self, version):
        """Initializer.

        Args:
          version: The PICO-8 data version from the game file header.
        """
        self._version = version
        self._tokens = []
        self._cur_lineno = 0
        self._cur_charno = 0

        # If inside a string literal (else None):
        # * the pos of the start of the string
        self._in_string_lineno = None
        self._in_string_charno = None
        # * a list of chars
        self._in_string = None
        # * the starting delimiter, either " or '
        self._in_string_delim = None

        # If inside a multiline comment (else None):
        # * the lines of comment, as an array of str (possibly empty)
        self._in_multiline_comment = None
        # * the pos of the start of the multiline comment
        self._in_multiline_comment_lineno = None
        self._in_multiline_comment_charno = None

        # If inside a multiline string (else None):
        # * the lines of string, as an array of str (possibly empty)
        self._in_multiline_string = None
        # The equals signs in [===...[, to match with closing delim.
        self._in_multiline_string_delim = None
        # * the pos of the start of the multiline comment
        self._in_multiline_string_lineno = None
        self._in_multiline_string_charno = None

    def _debug_lexer_state(self):
        return ''.join(
            '{}={}\n'.format(p, getattr(self, p)) for p in dir(self))

    def _process_token(self, s):
        """Process a token's worth of chars from a string, if possible.

        If a token is found, it is added to self._tokens. A call might
        process characters but not emit a token.

        Args:
          s: The string to process.

        Returns:
          The number of characters processed from the beginning of the string.
        """
        i = 0

        # TODO: PICO-8 doesn't allow literal newlines in quoted strings,
        # so this probably shouldn't either.
        if self._in_string is not None:
            # Continue string literal.
            while i < len(s):
                c = s[i:i+1]

                if c == self._in_string_delim:
                    # End string literal.
                    self._tokens.append(
                        TokString(b''.join(self._in_string),
                                  self._in_string_lineno,
                                  self._in_string_charno,
                                  quote=self._in_string_delim))
                    self._in_string_delim = None
                    self._in_string_lineno = None
                    self._in_string_charno = None
                    self._in_string = None
                    i += 1
                    break

                if c == b'\\':
                    # Escape character.
                    num_m = re.match(br'\d{1,3}', s[i+1:])
                    if num_m:
                        c = bytes([int(num_m.group(0))])
                        i += len(num_m.group(0))
                    else:
                        next_c = s[i+1:i+2]
                        if next_c in _STRING_ESCAPES:
                            c = _STRING_ESCAPES[next_c]
                            i += 1

                self._in_string.append(c)
                i += 1

        elif self._in_multiline_comment is not None:
            try:
                i = s.index(b']]') + 2
                self._in_multiline_comment.append(s[:i])
                self._tokens.append(
                    TokComment(b''.join(self._in_multiline_comment),
                               self._in_multiline_comment_lineno,
                               self._in_multiline_comment_charno))
                self._in_multiline_comment = None
                self._in_multiline_comment_lineno = None
                self._in_multiline_comment_charno = None

            except ValueError:
                self._in_multiline_comment.append(s)
                i = len(s)

        elif self._in_multiline_string is not None:
            m = re.search(br'\]' + self._in_multiline_string_delim + br'\]', s)
            if m:
                i = m.end()
                self._in_multiline_string.append(s[:m.start()])
                self._tokens.append(
                    TokString(b''.join(self._in_multiline_string),
                              self._in_multiline_string_lineno,
                              self._in_multiline_string_charno,
                              multiline_quote=self._in_multiline_string_delim))
                self._in_multiline_string = None
                self._in_multiline_string_delim = None
                self._in_multiline_string_lineno = None
                self._in_multiline_string_charno = None

            else:
                self._in_multiline_string.append(s)
                i = len(s)

        elif s.startswith(b'--[['):
            # (Multiline comments do not support the [===[ thing that
            # multiline strings do, so we can match directly.)
            self._in_multiline_comment = [b'--[[']
            self._in_multiline_comment_lineno = self._cur_lineno
            self._in_multiline_comment_charno = self._cur_charno
            i = 4

        elif re.match(br'\[=*\[', s):
            m = re.match(br'\[(=*)\[', s)
            i = m.end()
            self._in_multiline_string = []
            self._in_multiline_string_delim = m.group(1)
            self._in_multiline_string_lineno = self._cur_lineno
            self._in_multiline_string_charno = self._cur_charno

        elif s.startswith(b"'") or s.startswith(b'"'):
            # Begin string literal.
            self._in_string_delim = s[0:1]
            self._in_string_lineno = self._cur_lineno
            self._in_string_charno = self._cur_charno
            self._in_string = []
            i = 1

        else:
            # Match one-line patterns.
            for (pat, tok_class) in _TOKEN_MATCHERS:
                m = pat.match(s)
                if m:
                    if tok_class is not None:
                        token = tok_class(m.group(0),
                                          self._cur_lineno,
                                          self._cur_charno)
                        self._tokens.append(token)
                    i = len(m.group(0))
                    break

        for c in s[:i]:
            # (b'\n'[0] == 10)
            if c == b'\n'[0]:
                self._cur_lineno += 1
                self._cur_charno = 0
            else:
                self._cur_charno += 1
        return i

    def _process_line(self, line):
        """Processes a line of Lua source code.

        The line does not have to be a complete Lua statement or
        block. However, complete and valid code must have been
        processed before you can call a write_*() method.

        Args:
          line: The line of Lua source.

        Raises:
          LexerError: The line contains text that could not be mapped to known
            tokens (a syntax error).
        """
        i = 0
        while True:
            i = self._process_token(line)
            if i == 0:
                break
            line = line[i:]
        if line:
            util.debug('Lexer state:\n{}'.format(self._debug_lexer_state()))
            raise LexerError('Syntax error (remaining:%r)' % (line,),
                             self._cur_lineno + 1,
                             self._cur_charno + 1)

    def process_lines(self, lines):
        """Process lines of P8SCII Lua code.

        Args:
          lines: The Lua code to process, as an iterable of P8SCII bytestrings.
            Newline characters are expected to appear in the strings as they do
            in the original source, though each string in lines need not end
            with a newline.
        """
        for line in lines:
            self._process_line(line)

        if self._in_string is not None:
            raise LexerError('Unterminated string',
                             self._in_string_lineno,
                             self._in_string_charno)
        if self._in_multiline_string is not None:
            raise LexerError('Unterminated multiline string',
                             self._in_multiline_string_lineno,
                             self._in_multiline_string_charno)
        if self._in_multiline_comment is not None:
            # TODO: Allow unterminated multiline comments to just be comments.
            raise LexerError('Unterminated multiline comment',
                             self._in_multiline_comment_lineno,
                             self._in_multiline_comment_charno)

    @property
    def tokens(self):
        """The tokens produced by the lexer.

        This includes TokComment, TokSpace, and TokNewline
        tokens. These are not tokens of the Lua grammar, but are
        needed to reconstruct the original source with its formatting,
        or to reformat the original source while preserving comments
        and newlines.
        """
        return self._tokens
