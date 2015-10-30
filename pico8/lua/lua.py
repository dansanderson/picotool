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


PICO8_BUILTINS = {
    '_init', '_update', '_draw',
    'load', 'save', 'folder', 'ls', 'run', 'resume', 'reboot', 'stat', 'info',
    'flip', 'printh', 'clip', 'pget', 'pset', 'sget', 'sset', 'fget', 'fset',
    'print', 'cursor', 'color', 'cls', 'camera', 'circ', 'circfill', 'line',
    'rect', 'rectfill', 'pal', 'palt', 'spr', 'sspr', 'add', 'del', 'all',
    'foreach', 'pairs', 'btn', 'btnp', 'sfx', 'music', 'mget', 'mset', 'map',
    'peek', 'poke', 'memcpy', 'reload', 'cstore', 'memset', 'max', 'min', 'mid',
    'flr', 'cos', 'sin', 'atan2', 'sqrt', 'abs', 'rnd', 'srand', 'band', 'bor',
    'bxor', 'bnot', 'shl', 'shr', 'cartdata', 'dget', 'dset', 'sub', 'sgn',
    'count',  # deprecated function
    'mapdraw',  # deprecated function
    'self',   # a special name in Lua OO
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
            if t.matches(lexer.TokSymbol('...')):
                # Pico-8 counts triple-dot as three tokens.
                c += 3
            elif t.matches(lexer.TokSymbol('..')):
                # Pico-8 counts double-dot as two tokens.
                c += 2
            elif t.matches(lexer.TokSymbol(':')):
                # Pico-8 counts ':' as part of the method name token. Since
                # method names are the only case where picotool generates a ':'
                # TokSymbol, we simply don't count them.
                pass
            elif t.matches(lexer.TokNumber) and t._data.find('e') != -1:
                # Pico-8 counts 'e' part of number as a separate token.
                c += 2
            elif (not isinstance(t, lexer.TokSpace) and
                  not isinstance(t, lexer.TokNewline) and
                  not isinstance(t, lexer.TokComment)):
                c += 1
        if c == 0:
            # Pico-8 claims an empty (or comment-only) file has one token. This
            # isn't counted when there are other tokens, so it's a special case.
            c = 1
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
          lines: The Lua source, as an iterable of strings.
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
          lines: The Lua source, as an iterable of strings.
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
          A line of Lua code.
        """
        if writer_cls is None:
            writer_cls = LuaEchoWriter
        writer = writer_cls(tokens=self._lexer.tokens, root=self._parser.root,
                            args=writer_args)
        for line in writer.to_lines():
            yield line

            
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

    def _walk(self, node):
        """Walk a node by calling its handler.
        
        Yields:
          Items returned or yielded by the handler.
        """
        assert isinstance(node, parser.Node)
        result = getattr(self, '_walk_' + node.__class__.__name__)(node)
        if result is not None:
            for t in result:
                yield t

    def walk(self):
        """Walk an AST from the root.

        Yields:
          All items returned or yielded by the node handlers.
        """
        for t in self._walk(self._root):
            yield t

            
def _empty_node_handler(self, node):
    '''Empty node handler for BaseASTWalker that does nothing.'''
    pass


# For each node type, create an empty node handler in the base class.
for cname in dir(parser):
    cls = getattr(parser, cname)
    if isinstance(cls, type) and issubclass(cls, parser.Node):
        setattr(BaseASTWalker, '_walk_' + cls.__name__, _empty_node_handler)
            

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
                yield ''.join(strs)
                strs.clear()
        if strs:
            yield ''.join(strs)


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
          node: The Node with possible space and comment tokens in its range.

        Returns:
          A string representing the tokens.
        """
        strs = []
        while (((node is None and self._pos < len(self._tokens)) or
                (node is not None and self._pos < node.end_pos)) and
               (isinstance(self._tokens[self._pos], lexer.TokSpace) or
                isinstance(self._tokens[self._pos], lexer.TokNewline) or
                isinstance(self._tokens[self._pos], lexer.TokComment))):
            strs.append(self._tokens[self._pos].code)
            self._pos += 1
        return ''.join(strs)

    def _get_name(self, node, tok):
        """Gets the code for a TokName.

        A subclass can override this to transform names.

        Args:
          node: The Node containing the name.
          tok: The TokName token from the AST.

        Returns:
          The text for the name.
        """
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
        spaces_and_semis = []
        while True:
            spaces = self._get_code_for_spaces(node)
            if self._tokens[self._pos].matches(lexer.TokSymbol(';')):
                self._pos += 1
                spaces_and_semis.append(spaces + ';')
            else:
                spaces_and_semis.append(spaces)
                break
        return ''.join(spaces_and_semis)

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
        yield self._get_text(node, 'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, 'end')

    def _walk_StatWhile(self, node):
        yield self._get_text(node, 'while')
        for t in self._walk(node.exp):
            yield t
        yield self._get_text(node, 'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, 'end')

    def _walk_StatRepeat(self, node):
        yield self._get_text(node, 'repeat')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, 'until')
        for t in self._walk(node.exp):
            yield t

    def _walk_StatIf(self, node):
        short_if = getattr(node, 'short_if', False)
            
        first = True
        for (exp, block) in node.exp_block_pairs:
            if exp is not None:
                if first:
                    yield self._get_text(node, 'if')
                    first = False
                else:
                    yield self._get_text(node, 'elseif')
                if short_if:
                    yield self._get_text(node, '(')
                    self._indent += 1
                    for t in self._walk(exp):
                        yield t
                    self._indent -= 1
                    yield self._get_text(node, ')')
                else:
                    for t in self._walk(exp):
                        yield t
                    yield self._get_text(node, 'then')
                    self._indent += 1
                for t in self._walk(block):
                    yield t
                if not short_if:
                    self._indent -= 1
            else:
                yield self._get_text(node, 'else')
                self._indent += 1
                for t in self._walk(block):
                    yield t
                self._indent -= 1
        if not short_if:
            yield self._get_text(node, 'end')

    def _walk_StatForStep(self, node):
        yield self._get_text(node, 'for')
        yield self._get_name(node, node.name)
        yield self._get_text(node, '=')
        for t in self._walk(node.exp_init):
            yield t
        yield self._get_text(node, ',')
        for t in self._walk(node.exp_end):
            yield t
        if node.exp_step is not None:
            yield self._get_text(node, ',')
            for t in self._walk(node.exp_step):
                yield t
        yield self._get_text(node, 'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, 'end')

    def _walk_StatForIn(self, node):
        yield self._get_text(node, 'for')
        for t in self._walk(node.namelist):
            yield t
        yield self._get_text(node, 'in')
        for t in self._walk(node.explist):
            yield t
        yield self._get_text(node, 'do')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, 'end')

    def _walk_StatFunction(self, node):
        yield self._get_text(node, 'function')
        for t in self._walk(node.funcname):
            yield t
        for t in self._walk(node.funcbody):
            yield t

    def _walk_StatLocalFunction(self, node):
        yield self._get_text(node, 'local')
        yield self._get_text(node, 'function')
        yield self._get_name(node, node.funcname)
        for t in self._walk(node.funcbody):
            yield t

    def _walk_StatLocalAssignment(self, node):
        yield self._get_text(node, 'local')
        for t in self._walk(node.namelist):
            yield t
        if node.explist is not None:
            yield self._get_text(node, '=')
            for t in self._walk(node.explist):
                yield t

    def _walk_StatGoto(self, node):
        yield self._get_text(node, 'goto')
        yield self._get_name(node, lexer.TokName(node.label))

    def _walk_StatLabel(self, node):
        yield self._get_code_for_spaces(node)
        yield '::'
        yield self._get_name(node, lexer.TokName(node.label))
        yield '::'

    def _walk_StatBreak(self, node):
        yield self._get_text(node, 'break')

    def _walk_StatReturn(self, node):
        yield self._get_text(node, 'return')
        if node.explist is not None:
            for t in self._walk(node.explist):
                yield t

    def _walk_FunctionName(self, node):
        yield self._get_name(node, node.namepath[0])
        if len(node.namepath) > 1:
            for i in range(1, len(node.namepath)):
                yield self._get_text(node, '.')
                yield self._get_name(node, node.namepath[i])
        if node.methodname is not None:
            yield self._get_text(node, ':')
            yield self._get_name(node, node.methodname)

    def _walk_FunctionArgs(self, node):
        yield self._get_text(node, '(')
        self._indent += 1
        if node.explist is not None:
            for t in self._walk(node.explist):
                yield t
        self._indent -= 1
        yield self._get_text(node, ')')

    def _walk_VarList(self, node):
        for t in self._walk(node.vars[0]):
            yield t
        if len(node.vars) > 1:
            for i in range(1, len(node.vars)):
                yield self._get_text(node, ',')
                for t in self._walk(node.vars[i]):
                    yield t

    def _walk_VarName(self, node):
        yield self._get_name(node, node.name)

    def _walk_VarIndex(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        yield self._get_text(node, '[')
        self._indent += 1
        for t in self._walk(node.exp_index):
            yield t
        self._indent -= 1
        yield self._get_text(node, ']')

    def _walk_VarAttribute(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        yield self._get_text(node, '.')
        yield self._get_name(node, node.attr_name)

    def _walk_NameList(self, node):
        if node.names is not None:
            yield self._get_name(node, node.names[0])
            if len(node.names) > 1:
                for i in range(1, len(node.names)):
                    yield self._get_text(node, ',')
                    yield self._get_name(node, node.names[i])

    def _walk_ExpList(self, node):
        if node.exps is not None:
            for t in self._walk(node.exps[0]):
                yield t
            if len(node.exps) > 1:
                for i in range(1, len(node.exps)):
                    yield self._get_text(node, ',')
                    for t in self._walk(node.exps[i]):
                        yield t

    def _walk_ExpValue(self, node):
        yield self._get_code_for_spaces(node)
        in_parens = False
        if self._tokens[self._pos].matches(lexer.TokSymbol('(')):
            yield '('
            in_parens = True
            self._pos += 1
            self._indent += 1
        if node.value == None:
            yield self._get_text(node, 'nil')
        elif node.value == False:
            yield self._get_text(node, 'false')
        elif node.value == True:
            yield self._get_text(node, 'true')
        elif isinstance(node.value, lexer.TokName):
            yield self._get_name(node, node.value)
        elif (isinstance(node.value, lexer.TokNumber) or
              isinstance(node.value, lexer.TokString)):
            yield self._get_code_for_spaces(node)
            yield self._tokens[self._pos].code
            self._pos += 1
        else:
            for t in self._walk(node.value):
                yield t
        if in_parens:
            self._indent -= 1
            yield self._get_text(node, ')')

    def _walk_VarargDots(self, node):
        yield self._get_text(node, '...')

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
            yield self._get_text(node, '(')
            yield self._get_text(node, ')')
        elif isinstance(node.args, lexer.TokString):
            yield self._get_code_for_spaces(node)
            self._pos += 1
            yield node.args.code
        else:
            for t in self._walk(node.args):
                yield t

    def _walk_FunctionCallMethod(self, node):
        for t in self._walk(node.exp_prefix):
            yield t
        yield self._get_text(node, ':')
        yield self._get_name(node, node.methodname)
        if node.args is None:
            yield self._get_text(node, '(')
            yield self._get_text(node, ')')
        elif isinstance(node.args, lexer.TokString):
            yield self._get_code_for_spaces(node)
            assert node.args.matches(self._tokens[self._pos])
            self._pos += 1
            yield node.args.code
        else:
            # FunctionArgs or TableConstructor
            for t in self._walk(node.args):
                yield t

    def _walk_Function(self, node):
        yield self._get_text(node, 'function')
        for t in self._walk(node.funcbody):
            yield t

    def _walk_FunctionBody(self, node):
        yield self._get_text(node, '(')
        self._indent += 1
        if node.parlist is not None:
            for t in self._walk(node.parlist):
                yield t
            if node.dots is not None:
                yield self._get_text(node, ',')
                for t in self._walk(node.dots):
                    yield t
        else:
            if node.dots is not None:
                for t in self._walk(node.dots):
                    yield t
        self._indent -= 1
        yield self._get_text(node, ')')
        self._indent += 1
        for t in self._walk(node.block):
            yield t
        self._indent -= 1
        yield self._get_text(node, 'end')

    def _walk_TableConstructor(self, node):
        yield self._get_text(node, '{')
        self._indent += 1
        if node.fields:
            for t in self._walk(node.fields[0]):
                yield t
            if len(node.fields) > 1:
                for i in range(1, len(node.fields)):
                    # The parser doesn't store which field separator was
                    # used, so we have to find it in the token stream.
                    yield self._get_code_for_spaces(node)
                    yield self._get_text(node, self._tokens[self._pos].code)
                    for t in self._walk(node.fields[i]):
                        yield t
        # Process a trailing fieldsep, if any.
        self._indent -= 1
        yield self._get_code_for_spaces(node)
        if (self._tokens[self._pos].matches(lexer.TokSymbol(',')) or
            self._tokens[self._pos].matches(lexer.TokSymbol(';'))):
            yield self._get_text(node, self._tokens[self._pos].code)
        yield self._get_text(node, '}')

    def _walk_FieldExpKey(self, node):
        yield self._get_text(node, '[')
        self._indent += 1
        for t in self._walk(node.key_exp):
            yield t
        self._indent -= 1
        yield self._get_text(node, ']')
        yield self._get_text(node, '=')
        for t in self._walk(node.exp):
            yield t

    def _walk_FieldNamedKey(self, node):
        yield self._get_name(node, node.key_name)
        yield self._get_text(node, '=')
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
        for chunk in self.walk():
            parts = chunk.split('\n')
            while len(parts) > 1:
                linebuf.append(parts.pop(0))
                yield ''.join(linebuf) + '\n'
                linebuf.clear()
            linebuf.append(parts.pop(0))

        # Write the last line and any trailing spaces, as lines.
        last = ''.join(linebuf) + self._get_code_for_spaces(None)
        parts = last.split('\n')
        for i in range(len(parts)-1):
            yield parts[i] + '\n'
        if parts[-1]:
            yield parts[-1]
        

class LuaMinifyWriter(LuaASTEchoWriter):
    """Writes the Lua code to use a minimal number of characters.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_map = {}
        self._next_name_id = 0

    NAME_CHARS = 'abcdefghijklmnopqrstuvwxyz'
    PRESERVED_NAMES = lexer.LUA_KEYWORDS | PICO8_BUILTINS

    @classmethod
    def _name_for_id(cls, id):
        first = ''
        if id >= len(LuaMinifyWriter.NAME_CHARS):
            first = cls._name_for_id(int(id / len(LuaMinifyWriter.NAME_CHARS)))
        return first + (LuaMinifyWriter.NAME_CHARS[id % len(LuaMinifyWriter.NAME_CHARS)])
        
    def _get_name(self, node, tok):
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

        if tok.code in LuaMinifyWriter.PRESERVED_NAMES:
            return spaces + tok.code

        if tok.code not in self._name_map:
            new_name = None
            while True:
                new_name = self._name_for_id(self._next_name_id)
                self._next_name_id += 1
                if not new_name in LuaMinifyWriter.PRESERVED_NAMES:
                    break
            self._name_map[tok.code] = new_name
            util.debug('- minifying name "{}" to "{}"\n'.format(
                tok.code, new_name))
            
        return spaces + self._name_map[tok.code]
    
    def _get_code_for_spaces(self, node):
        """Calculates the minified text for the space and comment tokens that
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
            if not isinstance(self._tokens[self._pos], lexer.TokComment):
                strs.append(self._tokens[self._pos].code)
            self._pos += 1

        if ((start_pos == 0) or (self._pos == len(self._tokens))):
            # Eliminate all spaces at beginning and end of code.
            return ''
        
        spaces = ''.join(strs)
        spaces = re.sub(r'\t', ' ', spaces)      # one tab -> one space
        spaces = re.sub(r'\n +', '\n', spaces)   # leading spaces -> none
        spaces = re.sub(r' +\n', '\n', spaces)   # trailing spaces -> none
        spaces = re.sub(r'  +', ' ', spaces)     # multiple spaces -> one space
        spaces = re.sub(r'\n\n+', '\n', spaces)  # multiple newlines -> one newline

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
            if self._tokens[self._pos].matches(lexer.TokSymbol(';')):
                self._pos += 1
                # Insert a space where the semi was to prevent 'a;b' from
                # becoming 'ab'.
                # TODO: This is an extraneous space in cases where the
                # semicolon had a space before or after it.
                spaces_without_semis.append(spaces + ' ')
            else:
                spaces_without_semis.append(spaces)
                break
        return ''.join(spaces_without_semis)


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
        spaces = ''.join(strs)

        # Normalize space characters.
        spaces = re.sub(r'\t', ' ', spaces)
        spaces = re.sub(r'\r\n', '\n', spaces)
        spaces = re.sub(r'\n\r', '\n', spaces)
        spaces = re.sub(r'\r', '\n', spaces)
        
        # Delete trailing whitespace.
        spaces = re.sub(r' +\n', '\n', spaces)

        # If a comment is on the same line as previous, separate it by two
        # spaces.
        if start_pos != 0:
            spaces = re.sub(r'^ *--', '  --', spaces)

        # If a comment is on its own line, indent it at the indent level.
        spaces = re.sub(r'\n *--',
                        '\n' + ' ' * self._indent_mult * self._indent + '--',
                        spaces)
        if start_pos == 0:
            spaces = re.sub(r'^ *--', '--', spaces)

        # If next non-space is on its own line, indent it at the indent level.
        spaces = re.sub(r'\n *$', '\n' + ' ' * self._indent_mult * self._indent,
                        spaces)
        if start_pos == 0:
            spaces = re.sub(r'^ *$', '', spaces)

        # Collapse regions of 2+ consecutive newlines to 2 newlines.
        # TODO: two blank lines before function defs? classes?
        spaces = re.sub(r'\n\n+', '\n\n', spaces)

        # Remove excess trailing whitespace at end of file.
        if self._pos == len(self._tokens):
            spaces = re.sub(r'[ \n]+$', '\n', spaces)
        
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
