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
    def _get_code_for_spaces(self, node, start=None):
        """Calculates the text for the space and comment tokens that prefix the
        node.

        The base implementation returns text that represents all space and
        comment tokens verbatim.

        Args:
          node: The Node.
          start: The first token position to consider. If None, uses
            node.start_pos.

        Returns:
          Tuple: (prefix_text, next_pos), where next_pos is the position of the
            first non-space non-comment token.
        """
        if start is not None:
            pos = start
        else:
            pos = node.start_pos
        strs = []
        while (pos < node.end_pos and
               (isinstance(self._tokens[pos], lexer.TokSpace) or
                isinstance(self._tokens[pos], lexer.TokNewline) or
                isinstance(self._tokens[pos], lexer.TokComment))):
            strs.append(self._tokens[pos].code)
            pos += 1
        return (''.join(strs), pos)

    def _get_code_for_name(self, token):
        """Calculates the code for a TokName.

        A subclass can override this to transform names.

        Args:
          token: The TokName token.
        """
        return token.code
    
    def _get_code_for_node(self, node, start=None):
        """Calculates the code for a given AST node, including the preceding
        spaces and comments.

        Args:
          node: The Node.
          start: A starting token position at or before the first non-space
            non-comment token for the node. If None, uses node.start_pos. This
            is used when an outer node and the first inner node both have the
            same whitespace prefix, to prevent the prefix from being processed
            twice.

        Yields:
          Chunks of code for the node.
        """
        (prefix_text, pos) = self._get_code_for_spaces(node, start=start)
        yield prefix_text

        if isinstance(node, lexer.Chunk):
            for stat in node.stats:
                for t in self._get_code_for_node(stat, start=pos):
                    yield t
        
        elif isinstance(node, lexer.StatAssignment):
            for t in self._get_code_for_node(node.varlist, start=pos):
                yield t
            pos = node.varlist.end_pos
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            yield '='
            pos += 1
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            for t in self._get_code_for_node(node.explist, start=pos):
                yield t
        
        elif isinstance(node, lexer.StatFunctionCall):
            for t in self._get_code_for_node(node.functioncall, start=pos):
                yield t
        
        elif isinstance(node, lexer.StatDo):
            yield 'do'
            pos += 1
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            for t in self._get_code_for_node(node.block, start=pos):
                yield t
            pos = node.block.end_pos
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            yield 'end'
        
        elif isinstance(node, lexer.StatWhile):
            yield 'while'
            pos += 1
            for t in self._get_code_for_node(node.exp, start=pos):
                yield t
            pos = node.exp.end_pos
            yield 'do'
            pos += 1
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            for t in self._get_code_for_node(node.block, start=pos):
                yield t
            pos = node.block.end_pos
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            yield 'end'
        
        elif isinstance(node, lexer.StatRepeat):
            yield 'repeat'
            pos += 1
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            for t in self._get_code_for_node(node.block, start=pos):
                yield t
            pos = node.block.end_pos
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            yield 'until'
            pos += 1
            (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
            yield prefix_text
            for t in self._get_code_for_node(node.exp, start=pos):
                yield t
        
        elif isinstance(node, lexer.StatIf):
            # TODO: Have the parser annotate the node with short_if. This
            # method is a hack, and fails in the edge case of the short-if
            # having a long-if in its block.
            short_if = True
            for tok in self._tokens[node.start_pos:node.end_pos]:
                if tok.matches(lexer.TokKeyword('then')):
                    short_if = False
                    break
                
            first = True
            for (exp, block) in node.exp_block_pairs:
                if exp is not None:
                    if first:
                        yield 'if'
                        first = False
                    else:
                        yield 'elseif'
                    pos += 1
                    (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
                    yield prefix_text
                    if short_if:
                        yield '('
                        pos += 1
                        (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
                        yield prefix_text
                        for t in self._get_code_for_node(exp, start=pos):
                            yield t
                        pos = exp.end_pos
                        (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
                        yield prefix_text
                        yield ')'
                        pos += 1
                    if not short_if:
                        yield 'then'
                        pos += 1
                    (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
                    yield prefix_text
                    for t in self._get_code_for_node(block, start=pos):
                        yield t
                    pos = block.end_pos
                else:
                    yield 'else'
                    pos += 1
                    (prefix_text, pos) = self._get_code_for_spaces(node, start=pos)
                    yield prefix_text
                    for t in self._get_code_for_node(block, start=pos):
                        yield t
                    pos = block.end_pos
            if not short_if:
                yield 'end'
        
        elif isinstance(node, lexer.StatForStep):
            # 'name', 'exp_init', 'exp_end', 'exp_step', 'block'
            pass
        
        elif isinstance(node, lexer.StatForIn):
            # 'namelist', 'explist', 'block'
            pass
        
        elif isinstance(node, lexer.StatFunction):
            # 'funcname', 'funcbody'
            pass
        
        elif isinstance(node, lexer.StatLocalFunction):
            # 'funcname', 'funcbody'
            pass
        
        elif isinstance(node, lexer.StatLocalAssignment):
            # 'namelist', 'explist'
            pass
        
        elif isinstance(node, lexer.StatGoto):
            # 'label',
            pass
        
        elif isinstance(node, lexer.StatLabel):
            # 'label',
            pass
        
        elif isinstance(node, lexer.StatBreak):
            #
            pass
        
        elif isinstance(node, lexer.StatReturn):
            # 'explist',
            pass
        
        elif isinstance(node, lexer.FunctionName):
            # 'namepath', 'methodname'
            pass
        
        elif isinstance(node, lexer.FunctionArgs):
            # 'explist',
            pass
        
        elif isinstance(node, lexer.VarList):
            # 'vars',
            pass
        
        elif isinstance(node, lexer.VarName):
            # 'name',
            pass
        
        elif isinstance(node, lexer.VarIndex):
            # 'exp_prefix', 'exp_index'
            pass
        
        elif isinstance(node, lexer.VarAttribute):
            # 'exp_prefix', 'attr_name'
            pass
        
        elif isinstance(node, lexer.NameList):
            # 'names',
            pass
        
        elif isinstance(node, lexer.ExpList):
            # 'exps',
            pass
        
        elif isinstance(node, lexer.ExpValue):
            # 'value',
            pass
        
        elif isinstance(node, lexer.VarargDots):
            #
            pass
        
        elif isinstance(node, lexer.ExpBinOp):
            # 'exp1', 'binop', 'exp2'
            pass
        
        elif isinstance(node, lexer.ExpUnOp):
            # 'unop', 'exp'
            pass
        
        elif isinstance(node, lexer.FunctionCall):
            # 'exp_prefix', 'args'
            pass
        
        elif isinstance(node, lexer.FunctionCallMethod):
            # 'exp_prefix', 'methodname', 'args'
            pass
        
        elif isinstance(node, lexer.Function):
            # 'funcbody',
            pass
        
        elif isinstance(node, lexer.FunctionBody):
            # 'parlist', 'dots', 'block'
            pass
        
        elif isinstance(node, lexer.TableConstructor):
            # 'fields',
            pass
        
        elif isinstance(node, lexer.FieldExpKey):
            # 'key_exp', 'exp'
            pass
        
        elif isinstance(node, lexer.FieldNamedKey):
            # 'key_name', 'exp'
            pass
        
        elif isinstance(node, lexer.FieldExp):
            # 'exp',
            pass
          
        
    def to_lines(self):
        """Generates lines of Lua source based on the parser output.

        Yields:
          Lines of Lua code.
        """
        for chunk in self._get_code_for_node(self._root):
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
