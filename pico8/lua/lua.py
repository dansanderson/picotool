"""The Lua code for a game."""

__all__ = [
    'Lua',
    'PICO8_LUA_CHAR_LIMIT',
    'PICO8_LUA_TOKEN_LIMIT',
    'PICO8_LUA_COMPRESSED_CHAR_LIMIT',
    'PICO8_BUILTINS'
]


import re

from .. import util
from . import lexer
from . import parser


PICO8_LUA_CHAR_LIMIT = 32768
PICO8_LUA_TOKEN_LIMIT = 8192
PICO8_LUA_COMPRESSED_CHAR_LIMIT = 15360

# These are in the same order as they are found in the PICO-8 manual.
PICO8_BUILTINS = {
    # System
    b'load', b'save', b'folder', b'dir', b'ls', b'run', b'stop', b'resume',
    b'reboot', b'info', b'flip', b'printh', b'stat', b'extcmd',
    # Program Structure
    b'_update', b'_draw', b'_init', b'_update60',
    # Graphics
    b'clip', b'pget', b'pset', b'sget', b'sset', b'fget', b'fset', b'print', b'cursor',
    b'color', b'cls', b'camera', b'circ', b'circfill', b'line', b'rect', b'rectfill',
    b'pal', b'palt', b'spr', b'sspr', b'fillp',
    # Tables
    b'add', b'del', b'all', b'foreach', b'pairs',
    # Input
    b'btn', b'btnp',
    # Audio
    b'sfx', b'music',
    # Map
    b'mget', b'mset', b'map',
    # Memory
    b'peek', b'poke', b'peek4', b'poke4', b'memcpy', b'reload', b'cstore', b'memset',
    # Math
    b'max', b'min', b'mid', b'flr', b'ceil', b'cos', b'sin', b'atan2', b'sqrt', b'abs',
    b'rnd', b'srand', b'band', b'bor', b'bxor', b'bnot', b'rotl', b'rotr', b'shl',
    b'shr', b'lshr',
    # Custom Menu Items
    b'menuitem',
    # Strings
    b'sub',
    # Types
    b'type', b'tostr', b'tonum',
    # Cartridge Data
    b'cartdata', b'dget', b'dset',
    # Additional Lua Features
    b'setmetatable', b'getmetatable',
    b'cocreate', b'coresume', b'costatus', b'yield',
    # Mentioned In Manual (but not fully documented)
    b'assert', b'sgn',
    b'?',   # alias for "print"
    # Deprecated
    b'count',  # deprecated function
    b'mapdraw',  # deprecated function
    b'time',
    # Announced
    b'_update_buttons',  # announced for 30/60 fps compatibility but not yet used?
    # Lua
    b'self',   # a special name in Lua OO
    # Internal
    b'__index'  # internal function sometimes used by carts
}


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
        return sum(len(l) for l in self.to_lines())

    def get_token_count(self):
        c = 0
        for t in self._lexer._tokens:
            # TODO: As of 0.1.8, "1 .. 5" is three tokens, "1..5" is one token
            if (t.matches(lexer.TokSymbol(b':')) or
                    t.matches(lexer.TokSymbol(b'.')) or
                    t.matches(lexer.TokSymbol(b')')) or
                    t.matches(lexer.TokSymbol(b']')) or
                    t.matches(lexer.TokSymbol(b'}')) or
                    t.matches(lexer.TokKeyword(b'local')) or
                    t.matches(lexer.TokKeyword(b'end'))):
                # Pico-8 generously does not count these as tokens.
                pass
            elif t.matches(lexer.TokNumber) and t._data.find(b'e') != -1:
                # Pico-8 counts 'e' part of number as a separate token.
                c += 2
            elif (not isinstance(t, lexer.TokSpace) and
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
        """Produces a Lua data object from lines of Lua source.

        Args:
          lines: The Lua source, as an iterable of bytestrings.
          version: The Pico-8 data version from the game file header.

        Returns:
          A populated Lua instance.
        """
        result = Lua(version)
        result.update_from_lines(lines)
        return result

    def update_from_lines(self, lines):
        """Updates the parser data with new lines of Lua source.

        Args:
          lines: The Lua source, as an iterable of bytestrings.
        """
        self._lexer.process_lines(lines)
        self._parser.process_tokens(self._lexer.tokens)

    def to_lines(self, writer_cls=None, writer_args=None):
        """Generates lines of Lua source based on the parser output.

        Args:
          writer_cls: The writer class to use. If None, defaults to
            LuaEchoWriter.
          writer_args: Args for the writer.

        Yields:
          A line of Lua code, as a bytestring.
        """
        if writer_cls is None:
            writer_cls = LuaEchoWriter
        writer = writer_cls(tokens=self._lexer.tokens, root=self._parser.root,
                            args=writer_args)
        for line in writer.to_lines():
            yield line

    def reparse(self, writer_cls=None, writer_args=None):
        """Run the output of a Lua writer back through the parser, then re-store the tokens and parser.

        This is useful for updating the token stream after transforming the AST. When doing this, be sure to use a
        writer that doesn't use the token stream. (I usually reparse with LuaASTEchoWriter and ignore_tokens=True,
        then write it out through LuaMinifyTokenWriter to clean it up. When LuaFormatterWriter is better, that'd
        also be an option. Of course, this clobbers comments.)

        Args:
          writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          writer_args: Args to pass to the Lua writer.
        """
        new_lua = Lua.from_lines(
            self.to_lines(writer_cls=writer_cls,
                          writer_args=writer_args),
            version=self.version)
        self._lexer = new_lua._lexer
        self._parser = new_lua._parser


class BaseASTWalker():
    """A base class for AST walkers."""
    def __init__(self, tokens, root, args=None):
        """Initializer.

        Args:
          tokens: The lexer tokens.
          root: The root of the AST produced by the parser.
          args: Additional args for the writer.
        """
        self._tokens = tokens
        self._root = root
        self._args = args or {}

    def _walk_token(self, token):
        """Walk a field whose value is a token.

        The default implementation does nothing.

        Yields:
          An appropriate value, or None.
        """
        if False:
            yield

    def _walk_value(self, value):
        """Walk a field whose value is a simple value (such as a bool).

        The default implementation does nothing.

        Yields:
          An appropriate value, or None.
        """
        if False:
            yield

    def _walk(self, node):
        """Walk a node by calling its handler.
        
        Yields:
          Items returned or yielded by the handler.
        """
        if isinstance(node, parser.Node):
            result = getattr(self, '_walk_' + node.__class__.__name__)(node)
            if result is not None:
                for t in result:
                    yield t
        elif isinstance(node, lexer.Token):
            for t in self._walk_token(node):
                yield t
        elif hasattr(node, '__len__') and type(node) != str:
            for item in node:
                for t in self._walk(item):
                    yield t
        else:
            for t in self._walk_value(node):
                yield t

    def walk(self):
        """Walk an AST from the root.

        Yields:
          All items returned or yielded by the node handlers.
        """
        for t in self._walk(self._root):
            yield t


def _default_node_handler(self, node):
    '''Default node handler for BaseASTWalker that walks fields.'''
    for field in node._fields:
        for t in self._walk(getattr(node, field)):
            yield t


# For each node type, create an empty node handler in the base class.
for cname in dir(parser):
    cls = getattr(parser, cname)
    if isinstance(cls, type) and issubclass(cls, parser.Node):
        setattr(BaseASTWalker, '_walk_' + cls.__name__, _default_node_handler)


class BaseLuaWriter(BaseASTWalker):
    """A base class for Lua writers."""
    def to_lines(self):
        """Generates lines of Lua source based on the parser output.

        Yields:
          Lines of Lua code.
        """
        raise NotImplementedError


class LuaEchoWriter(BaseLuaWriter):
    """Writes the Lua code to be identical to the input based on the token
    stream.

    This ignores the parser and just writes out the string values of the
    original token stream.
    """
    def to_lines(self):
        """
        Yields:
          Lines of Lua code.
        """
        strs = []
        for token in self._tokens:
            strs.append(token.code)
            if token.matches(lexer.TokNewline):
                yield b''.join(strs)
                strs.clear()
        if strs:
            yield b''.join(strs)


class LuaASTEchoWriter(BaseLuaWriter):
    """Base implementation for writing Lua code based on the parser AST.

    The base implementation behaves identically to LuaEchoWriter. Subclasses
    can modify certain behaviors to transform the code based on the AST.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._pos = None
        self._indent = 0

    def _get_code_for_spaces(self, node):
        """Calculates the text for the space and comment tokens that prefix the
        node.

        The base implementation returns text that represents all space and
        comment tokens verbatim.

        Args:
          node: The Node with possible space and comment tokens in its range, or
            None to just get spaces from the current token position.

        Returns:
          A string representing the tokens.
        """
        if self._args.get('ignore_tokens'):
            return b'\n'

        strs = []
        while (((node is None and self._pos < len(self._tokens)) or
                (node is not None and self._pos < node.end_pos)) and
               (isinstance(self._tokens[self._pos], lexer.TokSpace) or
                isinstance(self._tokens[self._pos], lexer.TokNewline) or
                isinstance(self._tokens[self._pos], lexer.TokComment))):
            strs.append(self._tokens[self._pos].code)
            self._pos += 1
        return b''.join(strs)

    def _get_name(self, node, tok):
        """Gets the code for a TokName.

        A subclass can override this to transform names.

        Args:
          node: The Node containing the name.
          tok: The TokName token from the AST.

        Returns:
          The text for the name.
        """
        if self._args.get('ignore_tokens'):
            return b' ' + tok.code

        spaces = self._get_code_for_spaces(node)
        assert tok.matches(lexer.TokName)
        self._pos += 1
        return spaces + tok.code

    def _get_text(self, node, keyword):
        """Gets the preceding spaces and code for a TokKeyword or TokSymbol.

        Args:
          node: The Node containing the keyword.
          keyword: The expected keyword or symbol.

        Returns:
          The text for the keyword or symbol.
        """
        if self._args.get('ignore_tokens'):
            return b' ' + keyword

        spaces = self._get_code_for_spaces(node)
        assert (self._tokens[self._pos].matches(lexer.TokKeyword(keyword)) or
                self._tokens[self._pos].matches(lexer.TokSymbol(keyword)))
        self._pos += 1
        return spaces + keyword

    def _get_semis(self, node):
        """Gets semicolons from between statements.

        Args:
          node: The Node containing the semis.

        Returns:
          The text for the semicolons and preceding spaces.
        """
        if self._args.get('ignore_tokens'):
            return b' '

        spaces_and_semis = []
        while True:
            spaces = self._get_code_for_spaces(node)
            if self._tokens[self._pos].matches(lexer.TokSymbol(b';')):
                self._pos += 1
                spaces_and_semis.append(spaces + b';')
            else:
                spaces_and_semis.append(spaces)
                break
        return b''.join(spaces_and_semis)

    def _walk_Chunk(self, node):
        for stat in node.stats:
            yield self._get_semis(node)
            for t in self._walk(stat):
                yield t
        yield self._get_semis(node)

    def _walk_StatAssignment(self, node):
        for t in self._walk(node.varlist):
            yield t
        yield self._get_text(node, node.assignop.code)
        for t in self._walk(node.explist):
            yield t

    def _walk_StatFunctionCall(self, node):
        for t in self._walk(node.functioncall):
            yield t

    def _walk_StatDo(self, node):
        yield self._get_text(node, b'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, b'end')

    def _walk_StatWhile(self, node):
        yield self._get_text(node, b'while')
        for t in self._walk(node.exp):
            yield t
        yield self._get_text(node, b'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, b'end')

    def _walk_StatRepeat(self, node):
        yield self._get_text(node, b'repeat')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, b'until')
        for t in self._walk(node.exp):
            yield t

    def _walk_StatIf(self, node):
        # The ignore_tokens hack screws up spacing, so convert short ifs to
        # long ifs.
        short_if = (getattr(node, 'short_if', False) and
                    not self._args.get('ignore_tokens'))

        first = True
        for (exp, block) in node.exp_block_pairs:
            if exp is not None:
                if first:
                    yield self._get_text(node, b'if')
                    first = False
                else:
                    yield self._get_text(node, b'elseif')
                if short_if:
                    yield self._get_text(node, b'(')
                    self._indent += 1
                    for t in self._walk(exp):
                        yield t
                    self._indent -= 1
                    yield self._get_text(node, b')')
                else:
                    for t in self._walk(exp):
                        yield t
                    yield self._get_text(node, b'then')
                    self._indent += 1
                for t in self._walk(block):
                    yield t
                if not short_if:
                    self._indent -= 1
            else:
                yield self._get_text(node, b'else')
                self._indent += 1
                for t in self._walk(block):
                    yield t
                self._indent -= 1
        if not short_if:
            yield self._get_text(node, b'end')

    def _walk_StatForStep(self, node):
        yield self._get_text(node, b'for')
        yield self._get_name(node, node.name)
        yield self._get_text(node, b'=')
        for t in self._walk(node.exp_init):
            yield t
        yield self._get_text(node, b',')
        for t in self._walk(node.exp_end):
            yield t
        if node.exp_step is not None:
            yield self._get_text(node, b',')
            for t in self._walk(node.exp_step):
                yield t
        yield self._get_text(node, b'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, b'end')

    def _walk_StatForIn(self, node):
        yield self._get_text(node, b'for')
        for t in self._walk(node.namelist):
            yield t
        yield self._get_text(node, b'in')
        for t in self._walk(node.explist):
            yield t
        yield self._get_text(node, b'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, b'end')

    def _walk_StatFunction(self, node):
        yield self._get_text(node, b'function')
        for t in self._walk(node.funcname):
            yield t
        for t in self._walk(node.funcbody):
            yield t

    def _walk_StatLocalFunction(self, node):
        yield self._get_text(node, b'local')
        yield self._get_text(node, b'function')
        yield self._get_name(node, node.funcname)
        for t in self._walk(node.funcbody):
            yield t

    def _walk_StatLocalAssignment(self, node):
        yield self._get_text(node, b'local')
        for t in self._walk(node.namelist):
            yield t
        if node.explist is not None:
            yield self._get_text(node, b'=')
            for t in self._walk(node.explist):
                yield t

    def _walk_StatGoto(self, node):
        yield self._get_text(node, b'goto')
        yield self._get_name(node, lexer.TokName(node.label))

    def _walk_StatLabel(self, node):
        yield self._get_code_for_spaces(node)
        yield b'::'
        yield self._get_name(node, lexer.TokName(node.label))
        yield b'::'

    def _walk_StatBreak(self, node):
        yield self._get_text(node, b'break')

    def _walk_StatReturn(self, node):
        yield self._get_text(node, b'return')
        if node.explist is not None:
            for t in self._walk(node.explist):
                yield t

    def _walk_FunctionName(self, node):
        yield self._get_name(node, node.namepath[0])
        if len(node.namepath) > 1:
            for i in range(1, len(node.namepath)):
                yield self._get_text(node, b'.')
                yield self._get_name(node, node.namepath[i])
        if node.methodname is not None:
            yield self._get_text(node, b':')
            yield self._get_name(node, node.methodname)

    def _walk_FunctionArgs(self, node):
        yield self._get_text(node, b'(')
        self._indent += 1
        if node.explist is not None:
            for t in self._walk(node.explist):
                yield t
        self._indent -= 1
        yield self._get_text(node, b')')

    def _walk_VarList(self, node):
        for t in self._walk(node.vars[0]):
            yield t
        if len(node.vars) > 1:
            for i in range(1, len(node.vars)):
                yield self._get_text(node, b',')
                for t in self._walk(node.vars[i]):
                    yield t

    def _walk_VarName(self, node):
        yield self._get_name(node, node.name)

    def _walk_VarIndex(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        yield self._get_text(node, b'[')
        self._indent += 1
        for t in self._walk(node.exp_index):
            yield t
        self._indent -= 1
        yield self._get_text(node, b']')

    def _walk_VarAttribute(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        yield self._get_text(node, b'.')
        yield self._get_name(node, node.attr_name)

    def _walk_NameList(self, node):
        if node.names is not None:
            yield self._get_name(node, node.names[0])
            if len(node.names) > 1:
                for i in range(1, len(node.names)):
                    yield self._get_text(node, b',')
                    yield self._get_name(node, node.names[i])

    def _walk_ExpList(self, node):
        if node.exps is not None:
            for t in self._walk(node.exps[0]):
                yield t
            if len(node.exps) > 1:
                for i in range(1, len(node.exps)):
                    yield self._get_text(node, b',')
                    for t in self._walk(node.exps[i]):
                        yield t

    def _walk_ExpValue(self, node):
        yield self._get_code_for_spaces(node)

        in_parens = False
        if self._args.get('ignore_tokens'):
            # Use node.value type to determine whether exp needs parens.
            if isinstance(node.value, parser.Node):
                yield b'('
                in_parens = True
                self._indent += 1
        else:
            if self._tokens[self._pos].matches(lexer.TokSymbol(b'(')):
                yield b'('
                in_parens = True
                self._pos += 1
                self._indent += 1

        if node.value == None:
            yield self._get_text(node, b'nil')
        elif node.value == False:
            yield self._get_text(node, b'false')
        elif node.value == True:
            yield self._get_text(node, b'true')
        elif isinstance(node.value, lexer.TokName):
            yield self._get_name(node, node.value)
        elif (isinstance(node.value, lexer.TokNumber) or
              isinstance(node.value, lexer.TokString)):
            yield self._get_code_for_spaces(node)
            yield node.value.code
            if not self._args.get('ignore_tokens'):
                self._pos += 1
        else:
            for t in self._walk(node.value):
                yield t

        if in_parens:
            self._indent -= 1
            yield self._get_text(node, b')')

    def _walk_VarargDots(self, node):
        yield self._get_text(node, b'...')

    def _walk_ExpBinOp(self, node):
        for t in self._walk(node.exp1):
            yield t
        yield self._get_text(node, node.binop.code)
        for t in self._walk(node.exp2):
            yield t

    def _walk_ExpUnOp(self, node):
        yield self._get_text(node, node.unop.code)
        for t in self._walk(node.exp):
            yield t

    def _walk_FunctionCall(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        if node.args is None:
            yield self._get_text(node, b'(')
            yield self._get_text(node, b')')
        elif isinstance(node.args, lexer.TokString):
            yield self._get_code_for_spaces(node)
            if not self._args.get('ignore_tokens'):
                self._pos += 1
            yield node.args.code
        else:
            for t in self._walk(node.args):
                yield t

    def _walk_FunctionCallMethod(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        yield self._get_text(node, b':')
        yield self._get_name(node, node.methodname)
        if node.args is None:
            yield self._get_text(node, b'(')
            yield self._get_text(node, b')')
        elif isinstance(node.args, lexer.TokString):
            yield self._get_code_for_spaces(node)
            if not self._args.get('ignore_tokens'):
                assert node.args.matches(self._tokens[self._pos])
                self._pos += 1
            yield node.args.code
        else:
            # FunctionArgs or TableConstructor
            for t in self._walk(node.args):
                yield t

    def _walk_Function(self, node):
        yield self._get_text(node, b'function')
        for t in self._walk(node.funcbody):
            yield t

    def _walk_FunctionBody(self, node):
        yield self._get_text(node, b'(')
        self._indent += 1
        if node.parlist is not None:
            for t in self._walk(node.parlist):
                yield t
            if node.dots is not None:
                yield self._get_text(node, b',')
                for t in self._walk(node.dots):
                    yield t
        else:
            if node.dots is not None:
                for t in self._walk(node.dots):
                    yield t
        self._indent -= 1
        yield self._get_text(node, b')')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, b'end')

    def _walk_TableConstructor(self, node):
        yield self._get_text(node, b'{')
        self._indent += 1
        if node.fields:
            for t in self._walk(node.fields[0]):
                yield t
            if len(node.fields) > 1:
                for i in range(1, len(node.fields)):
                    # The parser doesn't store which field separator was
                    # used, so we have to find it in the token stream.
                    yield self._get_code_for_spaces(node)
                    if self._args.get('ignore_tokens'):
                        yield b', '
                    else:
                        yield self._get_text(node, self._tokens[self._pos].code)
                    for t in self._walk(node.fields[i]):
                        yield t
        # Process a trailing fieldsep, if any.
        self._indent -= 1
        yield self._get_code_for_spaces(node)
        if not self._args.get('ignore_tokens'):
            if (self._tokens[self._pos].matches(lexer.TokSymbol(b',')) or
                self._tokens[self._pos].matches(lexer.TokSymbol(b';'))):
                yield self._get_text(node, self._tokens[self._pos].code)
        yield self._get_text(node, b'}')

    def _walk_FieldExpKey(self, node):
        yield self._get_text(node, b'[')
        self._indent += 1
        for t in self._walk(node.key_exp):
            yield t
        self._indent -= 1
        yield self._get_text(node, b']')
        yield self._get_text(node, b'=')
        for t in self._walk(node.exp):
            yield t

    def _walk_FieldNamedKey(self, node):
        yield self._get_name(node, node.key_name)
        yield self._get_text(node, b'=')
        for t in self._walk(node.exp):
            yield t

    def _walk_FieldExp(self, node):
        for t in self._walk(node.exp):
            yield t

    def _walk(self, node):
        """Calculates the code for a given AST node, including the preceding
        spaces and comments.

        Args:
          node: The Node.

        Yields:
          Chunks of code for the node.
        """
        yield self._get_code_for_spaces(node)
        for t in super()._walk(node):
            yield t

    def to_lines(self):
        """Generates lines of Lua source based on the parser output.

        Yields:
          Lines of Lua code.
        """
        self._pos = 0

        linebuf = []
        last_was_newline = False
        for chunk in self.walk():
            if self._args.get('ignore_tokens'):
                # Clean up extraneous spacing.
                if chunk == b'\n':
                    if last_was_newline:
                        chunk = b''
                    last_was_newline = True
                else:
                    last_was_newline = False
            parts = chunk.split(b'\n')
            while len(parts) > 1:
                linebuf.append(parts.pop(0))
                yield b''.join(linebuf) + b'\n'
                linebuf.clear()
            linebuf.append(parts.pop(0))

        # Write the last line and any trailing spaces, as lines.
        last = b''.join(linebuf) + self._get_code_for_spaces(None)
        parts = last.split(b'\n')
        for i in range(len(parts)-1):
            yield parts[i] + b'\n'
        if parts[-1]:
            yield parts[-1]


class MinifyNameFactory():
    """Maps code names to generated short names."""
    NAME_CHARS = b'abcdefghijklmnopqrstuvwxyz'
    PRESERVED_NAMES = lexer.LUA_KEYWORDS | PICO8_BUILTINS

    def __init__(self):
        self._name_map = {}
        self._next_name_id = 0

    @classmethod
    def _name_for_id(cls, id):
        first = b''
        if id >= len(MinifyNameFactory.NAME_CHARS):
            first = cls._name_for_id(int(id / len(MinifyNameFactory.NAME_CHARS)))
        return first + bytes([MinifyNameFactory.NAME_CHARS[id % len(MinifyNameFactory.NAME_CHARS)]])

    def get_short_name(self, name, leave_it_be=False):
        if name in MinifyNameFactory.PRESERVED_NAMES:
            return name
        if name not in self._name_map:
            if leave_it_be:
                self._name_map[name] = name
                return name
            new_name = None
            while True:
                new_name = self._name_for_id(self._next_name_id)
                self._next_name_id += 1
                if not new_name in MinifyNameFactory.PRESERVED_NAMES:
                    break
            self._name_map[name] = new_name
            util.debug('- minifying name "{}" to "{}"\n'.format(
                name, new_name))
        return self._name_map[name]


class LuaMinifyWriter(LuaASTEchoWriter):
    """Writes the Lua code to use a minimal number of characters.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_factory = MinifyNameFactory()

    def _get_name(self, node, tok, leave_it_be=False):
        """Gets the minified name for a TokName.

        Args:
          node: The Node containing the name.
          tok: The TokName token from the AST.

        Returns:
          The text for the name.
        """
        spaces = self._get_code_for_spaces(node)
        assert tok.matches(lexer.TokName)
        self._pos += 1
        return spaces + self._name_factory.get_short_name(tok.code, leave_it_be)

    def _get_code_for_spaces(self, node):
        """Calculates the minified text for the space and comment tokens that
        prefix the node.

        Args:
          node: The Node with possible space and comment tokens in its range, or
            None to just get spaces from the current token position.

        Returns:
          A string representing the minified spaces.
        """
        start_pos = self._pos
        strs = []
        while (((node is None and self._pos < len(self._tokens)) or
                (node is not None and self._pos < node.end_pos)) and
               (isinstance(self._tokens[self._pos], lexer.TokSpace) or
                isinstance(self._tokens[self._pos], lexer.TokNewline) or
                isinstance(self._tokens[self._pos], lexer.TokComment))):
            if not isinstance(self._tokens[self._pos], lexer.TokComment):
                strs.append(self._tokens[self._pos].code)
            self._pos += 1

        if (start_pos == 0) or (self._pos == len(self._tokens)):
            # Eliminate all spaces at beginning and end of code.
            return b''

        spaces = b''.join(strs)
        spaces = re.sub(br'\t', b' ', spaces)      # one tab -> one space
        spaces = re.sub(br'\n +', b'\n', spaces)   # leading spaces -> none
        spaces = re.sub(br' +\n', b'\n', spaces)   # trailing spaces -> none
        spaces = re.sub(br'  +', b' ', spaces)     # multiple spaces -> one space
        spaces = re.sub(br'\n\n+', b'\n', spaces)  # multiple newlines -> one newline

        # TODO: Eliminate space between symbols and names/keywords on the same
        # line. (Use self._tokens[start_pos-1] and self._tokens[self._pos].)

        return spaces

    def _get_semis(self, node):
        """Skips semicolons between statements.

        Args:
          node: The Node containing the semis.

        Returns:
          The preceding spaces up to any semicolons, without the semicolons.
        """
        spaces_without_semis = []
        while True:
            spaces = self._get_code_for_spaces(node)
            if self._tokens[self._pos].matches(lexer.TokSymbol(b';')):
                self._pos += 1
                # Insert a space where the semi was to prevent 'a;b' from
                # becoming 'ab'.
                # TODO: This is an extraneous space in cases where the
                # semicolon had a space before or after it.
                spaces_without_semis.append(spaces + b' ')
            else:
                spaces_without_semis.append(spaces)
                break
        return b''.join(spaces_without_semis)

    def _walk_VarAttribute(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        yield self._get_text(node, b'.')
        yield self._get_name(node, node.attr_name, True)

    def _walk_FieldNamedKey(self, node):
        yield self._get_name(node, node.key_name, True)
        yield self._get_text(node, b'=')
        for t in self._walk(node.exp):
            yield t


class LuaFormatterWriter(LuaASTEchoWriter):
    """Writes the Lua code to use good spacing style.
    """
    DEFAULT_INDENT_WIDTH = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._indent_mult = self._args.get(
            'indentwidth',
            LuaFormatterWriter.DEFAULT_INDENT_WIDTH)

    def _get_code_for_spaces(self, node):
        """Calculates the formatted text for the space and comment tokens that
        prefix the node.

        Args:
          node: The Node with possible space and comment tokens in its range.

        Returns:
          A string representing the minified spaces.
        """
        start_pos = self._pos
        strs = []
        while (((node is None and self._pos < len(self._tokens)) or
                (node is not None and self._pos < node.end_pos)) and
               (isinstance(self._tokens[self._pos], lexer.TokSpace) or
                isinstance(self._tokens[self._pos], lexer.TokNewline) or
                isinstance(self._tokens[self._pos], lexer.TokComment))):
            strs.append(self._tokens[self._pos].code)
            self._pos += 1
        spaces = b''.join(strs)

        # Normalize space characters.
        spaces = re.sub(br'\t', b' ', spaces)
        spaces = re.sub(br'\r\n', b'\n', spaces)
        spaces = re.sub(br'\n\r', b'\n', spaces)
        spaces = re.sub(br'\r', b'\n', spaces)

        # Delete trailing whitespace.
        spaces = re.sub(br' +\n', b'\n', spaces)

        # If a comment is on the same line as previous, separate it by two
        # spaces.
        if start_pos != 0:
            spaces = re.sub(br'^ *--', b'  --', spaces)

        # If a comment is on its own line, indent it at the indent level.
        spaces = re.sub(br'\n *--',
                        b'\n' + b' ' * self._indent_mult * self._indent + b'--',
                        spaces)
        if start_pos == 0:
            spaces = re.sub(br'^ *--', b'--', spaces)

        # If next non-space is on its own line, indent it at the indent level.
        spaces = re.sub(br'\n *$', b'\n' + b' ' * self._indent_mult * self._indent,
                        spaces)
        if start_pos == 0:
            spaces = re.sub(br'^ *$', b'', spaces)

        # Collapse regions of 2+ consecutive newlines to 2 newlines.
        # TODO: two blank lines before function defs? classes?
        spaces = re.sub(br'\n\n+', b'\n\n', spaces)

        # Remove excess trailing whitespace at end of file.
        if self._pos == len(self._tokens):
            spaces = re.sub(br'[ \n]+$', b'\n', spaces)

        # TODO: same-line spacing patterns:
        # - one space before and after binop
        # - one space before unop, no space after (except "not")
        # - no space inside parens or braces
        # - no space to left of comma or semicolon; one space after
        # - no space around colons (for methods)
        # - no "empty" semicolon statements; non-empty semicolon should be
        #    adjacent to its statement
        # - block starts on a new line; 'end' always on its own line

        return spaces


class LuaMinifyTokenWriter(BaseLuaWriter):
    """Another minify writer.

    Unlike LuaMinifyWriter, this implementation just runs across the token stream and ignores the parser.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_factory = MinifyNameFactory()
        self._last_was_name_keyword_number = False
        self._last_was_newline = True
        self._approx_count = 0

    def to_lines(self):
        """
        Yields:
          Chunks of Lua code.
        """
        for token in self._tokens:
            if (token.matches(lexer.TokComment) or
                token.matches(lexer.TokSpace)) and self._approx_count > 2:
                # Strip out comments except for the first two which are significant
                # to PICO-8's cartridge creation system.
                continue
            elif token.matches(lexer.TokNewline):
                # Preserve non-consecutive newlines. This is the easiest way to handle Pico-8's newline-dependent
                # language extensions, especially short-ifs.
                self._last_was_name_keyword_number = False
                if not self._last_was_newline:
                    yield b'\n'
                self._last_was_newline = True
            elif token.matches(lexer.TokName):
                if self._last_was_name_keyword_number:
                    yield b' '
                self._last_was_name_keyword_number = True
                self._last_was_newline = False
                yield self._name_factory.get_short_name(token.code)
            elif token.matches(lexer.TokKeyword):
                if self._last_was_name_keyword_number:
                    yield b' '
                self._last_was_name_keyword_number = True
                self._last_was_newline = False
                yield token.code
            elif token.matches(lexer.TokNumber):
                if self._last_was_name_keyword_number:
                    yield b' '
                self._last_was_name_keyword_number = True
                self._last_was_newline = False
                yield token.code
            else:
                self._last_was_name_keyword_number = token.code in b'])}'
                self._last_was_newline = False
                yield token.code
            self._approx_count += 1


class LuaFormatterTokenWriter(LuaASTEchoWriter):
    """Another formatter writer.

    Unlike LuaFormatterWriter, this implementation just uses the token stream and ignores the parser.
    """
    DEFAULT_INDENT_WIDTH = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._indent_mult = self._args.get(
            'indentwidth',
            LuaFormatterWriter.DEFAULT_INDENT_WIDTH)

    def to_lines(self):
        """
        Yields:
            Chunks of code.
        """
        indent_level = 0
        space_buffer = []
        in_function = False
        previous_nonspace = None

        # TODO: short-if support

        for token in self._tokens:
            # Capture spaces and newlines.
            if token.matches(lexer.TokNewline):
                space_buffer.append(token)
                continue
            if token.matches(lexer.TokSpace):
                space_buffer.append(token)
                continue

            # Decrease the indentation level.
            if (any(token.matches(lexer.TokSymbol(s))
                    for s in (b')', b'}', b']')) or
                any(token.matches(lexer.TokKeyword(k))
                    for k in (b'end', b'until', b'elseif', b'else'))):
                indent_level -= 1

            # Rules for spaces and newlines:
            # * If the original source has two or more consecutive newlines,
            #    use two newlines.
            # * If a comment is on its own line, indent with source.
            # * If a comment is on a line with something else, offset by two spaces.
            # * Use no space before or after certain symbols.
            # * Use one space between tokens otherwise.
            #
            # This strategy puts some trust (perhaps too much) in the original source to use newlines and spaces
            # according to the author's wishes for the formatted output. We're not using the parser, so we can't
            # make our own decisions based on statements, argument lists, etc. We also don't wrap lines, but this
            # strategy doesn't usually add space.
            #
            # Known issues:
            # * unary minus gets a space, shouldn't
            # * no short-if support!
            space_str = b''.join(t.code for t in space_buffer)
            space_buffer.clear()
            newline_count = space_str.count(b'\n')
            if newline_count:
                if newline_count > 1:
                    yield b'\n'
                yield b'\n' + b' ' * indent_level * self._indent_mult
            elif token.matches(lexer.TokComment):
                yield b'  '
            elif (any(token.matches(lexer.TokSymbol(s))
                      for s in (b',', b';', b')', b']', b'}', b'..')) or
                  (previous_nonspace is not None and
                   any(previous_nonspace.matches(lexer.TokSymbol(s))
                       for s in (b'(', b'[', b'{', b'..'))) or
                  (previous_nonspace is not None and
                   previous_nonspace.matches(lexer.TokKeyword(b'function')) and
                   token.matches(lexer.TokSymbol(b'('))) or
                  previous_nonspace is None):
                # No space before or after certain symbols.
                pass
            else:
                yield b' '

            # Write the nonspace token.
            previous_nonspace = token
            yield token.code

            # Increase the indentation level.
            if in_function and token.matches(lexer.TokSymbol(b')')):
                in_function = False
                indent_level += 1  # matched by "end"
            if token.matches(lexer.TokKeyword(b'function')):
                in_function = True

            if (any(token.matches(lexer.TokSymbol(s))
                    for s in (b'(', b'{', b'[')) or
                any(token.matches(lexer.TokKeyword(k))
                    for k in (b'do', b'repeat', b'then', b'else'))):
                indent_level += 1

        yield b'\n'
