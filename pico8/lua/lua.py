"""The Lua code for a game."""

__all__ = [
    'Lua',
    'PICO8_LUA_CHAR_LIMIT',
    'PICO8_LUA_TOKEN_LIMIT',
    'PICO8_LUA_COMPRESSED_CHAR_LIMIT'
]

from . import lexer
from . import parser


PICO8_LUA_CHAR_LIMIT = 32768
PICO8_LUA_TOKEN_LIMIT = 8192
PICO8_LUA_COMPRESSED_CHAR_LIMIT = 15360


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
    def __init__(self):
        super().__init__()

        self._pos = None
        
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
        while (self._pos < node.end_pos and
               (isinstance(self._tokens[self._pos], lexer.TokSpace) or
                isinstance(self._tokens[self._pos], lexer.TokNewline) or
                isinstance(self._tokens[self._pos], lexer.TokComment))):
            strs.append(self._tokens[self._pos].code)
            self._pos += 1
        return ''.join(strs)

    def _get_name(self, node, tok):
        """Gets the code for a TokName or TokNumber.

        A subclass can override this to transform names.

        Args:
          node: The Node containing the name.
          tok: The TokName or TokNumber token from the AST.

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
    
    def _generate_code_for_node(self, node):
        """Calculates the code for a given AST node, including the preceding
        spaces and comments.

        Args:
          node: The Node.

        Yields:
          Chunks of code for the node.
        """
        yield self._get_code_for_spaces(node)

        if isinstance(node, lexer.Chunk):
            for stat in node.stats:
                for t in self._generate_code_for_node(stat):
                    yield t
        
        elif isinstance(node, lexer.StatAssignment):
            for t in self._generate_code_for_node(node.varlist):
                yield t
            yield self._get_text(node, '=')
            for t in self._generate_code_for_node(node.explist):
                yield t
        
        elif isinstance(node, lexer.StatFunctionCall):
            for t in self._generate_code_for_node(node.functioncall):
                yield t
        
        elif isinstance(node, lexer.StatDo):
            yield self._get_text(node, 'do')
            for t in self._generate_code_for_node(node.block):
                yield t
            yield self._get_text(node, 'end')
            
        elif isinstance(node, lexer.StatWhile):
            yield self._get_text(node, 'while')
            for t in self._generate_code_for_node(node.exp):
                yield t
            yield self._get_text(node, 'do')
            for t in self._generate_code_for_node(node.block):
                yield t
            yield self._get_text(node, 'end')
        
        elif isinstance(node, lexer.StatRepeat):
            yield self._get_text(node, 'repeat')
            for t in self._generate_code_for_node(node.block):
                yield t
            yield self._get_text(node, 'until')
            for t in self._generate_code_for_node(node.exp):
                yield t
        
        elif isinstance(node, lexer.StatIf):
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
                        for t in self._generate_code_for_node(exp):
                            yield t
                        yield self._get_text(node, ')')
                    if not short_if:
                        yield self._get_text(node, 'then')
                    for t in self._generate_code_for_node(block):
                        yield t
                else:
                    yield self._get_text(node, 'else')
                    for t in self._generate_code_for_node(block):
                        yield t
            if not short_if:
                yield self._get_text(node, 'end')
        
        elif isinstance(node, lexer.StatForStep):
            yield self._get_text(node, 'for')
            yield self._get_name(node, node.name)
            yield self._get_text(node, '=')
            for t in self._generate_code_for_node(node.exp_init):
                yield t
            yield self._get_text(node, ',')
            for t in self._generate_code_for_node(node.exp_end):
                yield t
            if node.exp_step is not None:
                yield self._get_text(node, ',')
                for t in self._generate_code_for_node(node.exp_step):
                    yield t
            yield self._get_text(node, 'do')
            for t in self._generate_code_for_node(node.block):
                yield t
            yield self._get_text(node, 'end')
        
        elif isinstance(node, lexer.StatForIn):
            yield self._get_text(node, 'for')
            for t in self._generate_code_for_node(node.namelist):
                yield t
            yield self._get_text(node, 'in')
            for t in self._generate_code_for_node(node.explist):
                yield t
            yield self._get_text(node, 'do')
            for t in self._generate_code_for_node(node.block):
                yield t
            yield self._get_text(node, 'end')
        
        elif isinstance(node, lexer.StatFunction):
            yield self._get_text(node, 'function')
            for t in self._generate_code_for_node(node.funcname):
                yield t
            for t in self._generate_code_for_node(node.funcbody):
                yield t
        
        elif isinstance(node, lexer.StatLocalFunction):
            yield self._get_text(node, 'local')
            yield self._get_text(node, 'function')
            for t in self._generate_code_for_node(node.funcname):
                yield t
            for t in self._generate_code_for_node(node.funcbody):
                yield t
        
        elif isinstance(node, lexer.StatLocalAssignment):
            yield self._get_text(node, 'local')
            for t in self._generate_code_for_node(node.namelist):
                yield t
            if node.explist is not None:
                yield self._get_text(node, '=')
                for t in self._generate_code_for_node(node.explist):
                    yield t
        
        elif isinstance(node, lexer.StatGoto):
            yield self._get_text(node, 'goto')
            yield self._get_name(node, node.label)
        
        elif isinstance(node, lexer.StatLabel):
            yield self._get_code_for_spaces(node)
            yield '::'
            yield self._get_name(node, node.label)
            yield '::'
        
        elif isinstance(node, lexer.StatBreak):
            yield self._get_text(node, 'break')
        
        elif isinstance(node, lexer.StatReturn):
            yield self._get_text(node, 'return')
            if node.explist is not None:
                for t in self._generate_code_for_node(node.explist):
                    yield t
        
        elif isinstance(node, lexer.FunctionName):
            yield self._get_name(node, node.namepath[0])
            if len(node.namepath) > 1:
                for i in range(1, len(node.namepath)):
                    yield self._get_text(node, '.')
                    yield self._get_name(node, node.namepath[i])
            if node.methodname is not None:
                yield self._get_text(node, ':')
                yield self._get_name(node, node.methodname)
        
        elif isinstance(node, lexer.FunctionArgs):
            yield self._get_text(node, '(')
            for t in self._generate_code_for_node(node.explist):
                yield t
            yield self._get_text(node, ')')
        
        elif isinstance(node, lexer.VarList):
            for t in self._generate_code_for_node(node.vars[0]):
                yield t
            if len(node.vars) > 1:
                for i in range(1, node.vars):
                    yield self._get_text(node, ',')
                    for t in self._generate_code_for_node(node.vars[i]):
                        yield t
        
        elif isinstance(node, lexer.VarName):
            yield self._get_name(node, node.name)
        
        elif isinstance(node, lexer.VarIndex):
            for t in self._generate_code_for_node(node.exp_prefix):
                yield t
            yield self._get_text(node, '[')
            for t in self._generate_code_for_node(node.exp_index):
                yield t
            yield self._get_text(node, ']')
        
        elif isinstance(node, lexer.VarAttribute):
            for t in self._generate_code_for_node(node.exp_prefix):
                yield t
            yield self._get_text(node, '.')
            yield self._get_name(node, node.attr_name)
        
        elif isinstance(node, lexer.NameList):
            if node.names is not None:
                yield self._get_name(node, node.names[0])
                if len(node.names) > 1:
                    for i in range(1, len(node.names)):
                        yield self._get_text(node, ',')
                        yield self._get_name(node, node.names[i])
        
        elif isinstance(node, lexer.ExpList):
            if node.exps is not None:
                for t in self._generate_code_for_node(node.exps[0]):
                    yield t
                if len(node.exps) > 1:
                    for i in range(1, len(node.exps)):
                        for t in self._generate_code_for_node(node.exps[i]):
                            yield t
        
        elif isinstance(node, lexer.ExpValue):
            if node.value == None:
                yield self._get_text(node, 'nil')
            elif node.value == False:
                yield self._get_text(node, 'false')
            elif node.value == True:
                yield self._get_text(node, 'true')
            elif isinstance(node.value, str):
                # TokName or TokNumber
                yield self._get_name(node, node.value)
            else:
                for t in self._generate_code_for_node(node.value):
                    yield t
        
        elif isinstance(node, lexer.VarargDots):
            yield self._get_text(node, '...')
        
        elif isinstance(node, lexer.ExpBinOp):
            for t in self._generate_code_for_node(node.exp1):
                yield t
            yield self._get_text(node.binop.code)
            for t in self._generate_code_for_node(node.exp2):
                yield t
        
        elif isinstance(node, lexer.ExpUnOp):
            yield self._get_text(node.unop.code)
            for t in self._generate_code_for_node(node.exp):
                yield t
        
        elif isinstance(node, lexer.FunctionCall):
            for t in self._generate_code_for_node(node.exp_prefix):
                yield t
            if args is None:
                yield self._get_text(node, '(')
                yield self._get_text(node, ')')
            elif isinstance(args, str):
                # args is the parsed string, but we need the original token to
                # recreate the escaped string with its original punctuation.
                yield self._get_code_for_spaces(node)
                yield self._tokens[self._pos].code
            else:
                for t in self._generate_code_for_node(node.args):
                    yield t
        
        elif isinstance(node, lexer.FunctionCallMethod):
            for t in self._generate_code_for_node(node.exp_prefix):
                yield t
            yield self._get_text(node, ':')
            yield self._get_name(node, node.methodname)
            if args is None:
                yield self._get_text(node, '(')
                yield self._get_text(node, ')')
            elif isinstance(args, str):
                # args is the parsed string, but we need the original token to
                # recreate the escaped string with its original punctuation.
                yield self._get_code_for_spaces(node)
                yield self._tokens[self._pos].code
            else:
                for t in self._generate_code_for_node(node.args):
                    yield t
        
        elif isinstance(node, lexer.Function):
            yield self._get_text(node, 'function')
            for t in self._generate_code_for_node(node.funcbody):
                yield t
        
        elif isinstance(node, lexer.FunctionBody):
            yield self._get_text(node, '(')
            if node.parlist is not None:
                for t in self._generate_code_for_node(node.parlist):
                    yield t
                if node.dots is not None:
                    self._get_text(node, ',')
                    for t in self._generate_code_for_node(node.dots):
                        yield t
            else:
                if node.dots is not None:
                    for t in self._generate_code_for_node(node.dots):
                        yield t
            yield self._get_text(node, ')')
            for t in self._generate_code_for_node(node.block):
                yield t
            yield self._get_text(node, 'end')
        
        elif isinstance(node, lexer.TableConstructor):
            yield self._get_text(node, '{')
            if node.fields:
                for t in self._generate_code_for_node(node.fields[0]):
                    yield t
                if len(node.fields) > 1:
                    for i in range(1, len(node.fields)):
                        # The parser doesn't store which field separator was used,
                        # so we have to find it in the token stream.
                        yield self._get_code_for_spaces(node)
                        yield self._get_text(node, self._tokens[self._pos].code)
                        for t in self._generate_code_for_node(node.fields[i]):
                            yield t
            yield self._get_text(node, '}')
        
        elif isinstance(node, lexer.FieldExpKey):
            yield self._get_text(node, '[')
            for t in self._generate_code_for_node(node.key_exp):
                yield t
            yield self._get_text(node, ']')
            yield self._get_text(node, '=')
            for t in self._generate_code_for_node(node.exp):
                yield t
        
        elif isinstance(node, lexer.FieldNamedKey):
            yield self._get_name(node, node.key_name)
            yield self._get_text(node, '=')
            for t in self._generate_code_for_node(node.exp):
                yield t
        
        elif isinstance(node, lexer.FieldExp):
            for t in self._generate_code_for_node(node.exp):
                yield t
          
    def to_lines(self):
        """Generates lines of Lua source based on the parser output.

        Yields:
          Lines of Lua code.
        """
        self._pos = 0
        
        for chunk in self._generate_code_for_node(self._root):
            for l in chunk.split('\n'):
                yield l + '\n'


class LuaMinifyWriter(LuaASTEchoWriter):
    """Writes the Lua code to use a minimal number of characters.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_map = {}
        self._next_name_id = 0

    NAME_CHARS = 'abcdefghijklmnopqrstuvwxyz'
    @classmethod
    def _name_for_id(cls, id):
        first = ''
        if id > 26:
            first = cls._name_for_id(int(id / len(NAME_CHARS)))
        return first + (NAME_CHARS[id % len(NAME_CHARS)])
        
    def _get_code_for_name(self, token):
        if token.code not in self._name_map:
            self._name_map[token.code] = self._name_for_id(self._next_name_id)
            self._next_name_id += 1
        return self._name_map[token.code]
    
    def _get_code_for_spaces(self, node):
        # TODO: Track last-seen states, skip comments, compress space and newlines
        pos = node.start_pos
        strs = []
        while (pos < node.end_pos and
               (isinstance(self._tokens[pos], lexer.TokSpace) or
                isinstance(self._tokens[pos], lexer.TokNewline) or
                isinstance(self._tokens[pos], lexer.TokComment))):
            strs.append(self._tokens[pos].code)
            pos += 1
        return (''.join(strs), pos)


class LuaFormatterWriter(LuaASTEchoWriter):
    """Writes the Lua code to use good spacing style.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def _get_code_for_spaces(self, node):
        # TODO: Track indent level, preserve comments, render new space and nelines
        pos = node.start_pos
        strs = []
        while (pos < node.end_pos and
               (isinstance(self._tokens[pos], lexer.TokSpace) or
                isinstance(self._tokens[pos], lexer.TokNewline) or
                isinstance(self._tokens[pos], lexer.TokComment))):
            strs.append(self._tokens[pos].code)
            pos += 1
        return (''.join(strs), pos)
