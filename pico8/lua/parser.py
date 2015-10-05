"""The Lua parser."""

from .. import util
from . import lexer


__all__ = [
    'ParserError',
]


class ParserError(util.InvalidP8DataError):
    """A lexer error."""
    def __init__(self, msg, token=None):
        self.msg = msg
        self.token = token
        
    def __str__(self):
        if self.token is None:
            return '{} at end of file'.format(self.msg)
        return '{} at line {} char {}'.format(
            self.msg, self.token.lineno, self.token.charno)


class TokenBuffer():
    """A buffered token stream.

    The parser uses the token buffer for backtracking in an otherwise
    non-rewindable token stream. A production calls accept() to match
    terminal productions. If the full production needs to backtrack to
    the beginning of the current production, it calls rewind(). Once a
    full production is matched and it is no longer necessary to
    backtrack, it calls advance(). advance() both sets the reset point
    and truncates the buffer to free up memory.
    """

    # TODO: ability to configure TokenBuffer to skip whitespace, comments?
    # TODO: need to better understand the needs of backtracking; one bookmark
    #   might not be enough
    
    def __init__(self, token_iter):
        """Initializer.

        Args:
          token_iter: An iterable that generates tokens.
        """
        self._token_iter = token_iter

        # The position of the cursor. The cursor points to the next
        # token, i.e. the token returned by peek() or matched by
        # accept(). The value is an absolute index from the beginning
        # of the token stream.
        self._pos = 0

        # The cursor position of the first item in the buffer.
        self._bufpos = 0

        # The token buffer.
        self._tokenbuf = []

    def _buffer_to_pos(self, pos):
        """Load tokens from the token stream into the buffer.

        Args:
          pos: The absolute token position to buffer. Must be > self._bufpos.

        Raises:
          StopIteration: The token stream ran out of tokens before we reached
            pos. Max pos = self._bufpos + len(self._tokenbuf).
        """
        assert pos > self._bufpos
        while self._pos >= self._bufpos + len(self._tokenbuf):
            new_tok = self._token_iter.__next__()
            self._tokenbuf.append(new_tok)
            
    def peek(self):
        """Return the token under the cursor.

        Returns:
          The token under the cursor, or None if there is no next token.
        """
        try:
            self._buffer_to_pos(self._pos + 1)
        except StopIteration:
            return None
        return self._tokenbuf[self._pos - self._bufpos]

    def accept(self, tok_pattern):
        """Match the token under the cursor, and advance the cursor if matched.

        Args:
          tok_pattern: The lexer.Token subclass or subclass instance
            to match. If tok is a subclass, the current token matches
            if it has the same subclass. If tok is an instance, the
            current token matches if it has the same subclass and
            equal data.

        Returns:
          The token under the cursor if it matches, otherwise None.
        """
        cur_tok = self.peek()
        if cur_tok is not None and cur_tok.matches(tok_pattern):
            self._pos += 1
            return cur_tok
        return None
        
    def rewind(self):
        """Rewind the cursor to the last advance() call."""
        self._pos = self._bufpos
        
    def advance(self):
        """Advance the rewind position to the cursor.

        The parser calls advance() when a production generates an AST
        node. Prior to that point, the parser can call rewind() to
        move the cursor back to the location of the previous call to
        advance() (backtracking).
        """
        try:
            self._buffer_to_pos(self._pos)
        except StopIteration:
            self._pos = self._bufpos + len(self._tokenbuf)
        self._tokenbuf = self._tokenbuf[self._pos - self._bufpos:]
        self._bufpos = self._pos


class Node():
    """A base class for all AST nodes."""
    pass


# These are all Node subclasses that initialize members with
# (required) positional arguments. They are created and added to the
# module's namespace in the loop below the list.
#
# TODO: capture newline tokens between statements (def of chunk?)
# TODO: capture comment tokens as part of every node
_ast_node_types = (
    ('Chunk', ('stats',)),
    ('StatAssignment', ('varlist', 'explist')),
    ('StatFunctionCall', ('functioncall',)),
    ('StatDo', ('block',)),
    ('StatWhile', ('exp', 'block')),
    ('StatRepeat', ('block', 'exp')),
    ('StatIf', ('exp_block_pairs',)),
    ('StatForStep', ('name', 'exp_init', 'exp_end', 'exp_step', 'block')),
    ('StatForIn', ('namelist', 'explist', 'block')),
    ('StatFunction', ('funcname', 'funcbody')),
    ('StatLocalFunction', ('funcname', 'funcbody')),
    ('StatLocalAssignment', ('namelist', 'explist')),
    ('StatBreak', (,)),
    ('StatReturn', ('explist',)),
    ('FunctionName', ('namepath', 'methodname')),
    ('VarList', ('vars',)),
    ('VarName', ('name',)),
    ('VarIndex', ('exp_prefix', 'exp_index')),
    ('VarAttribute', ('exp_prefix', 'attr_name')),
    ('NameList', ('names',)),
    ('ExpList', ('exps',)),

    # value: None, False, True, number, string, Function, TableConstructor,
    #   Var*, FunctionCall, Exp*
    ('ExpValue', ('value',)),

    ('ExpDots', (,)),  # TODO: what is this called?
    ('ExpBinOp', ('exp1', 'binop', 'exp2')),
    ('ExpUnOp', ('unop', 'exp')),
    ('FunctionCall', ('exp_prefix', 'args')),
    ('FunctionCallMethod', ('exp_prefix', 'methodname', 'args')),
    ('Function', ('funcbody',)),

    # parlist: [name, ... [, ExpDots]]
    ('FunctionBody', ('parlist', 'block')),

    ('TableConstructor', ('fields',)),
    ('FieldOtherThing', ('exp1', 'exp2')),  # TODO: what is this called?
    ('FieldNamed', ('name', 'exp')),
    ('FieldExp', ('exp')),
)
for (name, fields) in _ast_node_types:
    def node_init(self, prefix_space_tokens=None, *args):
        self._prefix_space_tokens = prefix_space_tokens
        if len(args) != len(fields):
            raise TypeError(
                'Initializer for {} requires {} fields, saw {}'.format(
                    name, len(fields), len(args)))
        for i in range(len(fields)):
            setattr(self, fields[i], args[i])
    cls = type(name, (Node,), {'__init__': node_init})
    globals()[name] = cls

    
class Parser():
    """The parser."""

    def __init__(self, version):
        """Initializer.

        Args:
          version: The Pico-8 data version from the game file header.
        """
        self._version = version
        self._buf = None

    def _expect(self, tok_pattern):
        """Accept a token, or raise a ParserError if not found.

        Args:
          tok_pattern: The lexer.Token subclass or subclass instance
            to match, as described by TokenBuffer.accept().

        Returns:
          The token under the cursor if it matches, otherwise None.

        Raises:
          ParserError: The pattern doesn't match the next token.
        """
        tok = self._buf.accept(tok_pattern)
        if tok is not None:
            return tok
        if isinstance(tok_pattern, type):
            # TODO: Nicer error message instead of "TokFoo".
            raise ParserError('Expected {}'.format(tok_pattern.__name__),
                              token=self._buf.peek())
        raise ParserError('Expected {}'.format(tok_pattern.data),
                          token=self._buf.peek())

    def _spaces(self):
        """Accept zero or more whitespace, newline, and comment tokens.

        Returns:
          A list of zero or more whitespace, newline, and comment tokens.
        """
        space_tokens = []
        while True:
            tok = self._buf.accept(lexer.TokSpace)
            if tok is None:
                tok = self._buf.accept(lexer.TokNewline)
            if tok is None:
                self._buf.accept(lexer.TokComment)
            if tok is None:
                break
            space_tokens.append(tok)
        return space_tokens
        
    def _chunk(self):
        """Parse a chunk / block.
        
        chunk :: = {stat [';']} [laststat [';']]

        Returns:
          Chunk(stats)
        """
        stats = []
        while True:
            stat = self._stat()
            if stat is None:
                break
            stats.append(stat)
        laststat = self._laststat()
        if laststat is not None:
            stats.append(laststat)
        return Chunk(stats)

    def _stat(self):
        """Parse a stat.

        stat ::=  varlist `=´ explist | 
		 functioncall | 
		 do block end | 
		 while exp do block end | 
		 repeat block until exp | 
		 if exp then block {elseif exp then block} [else block] end | 
		 for Name `=´ exp `,´ exp [`,´ exp] do block end | 
		 for namelist in explist do block end | 
		 function funcname funcbody | 
		 local function Name funcbody | 
		 local namelist [`=´ explist]

        Returns:
          StatAssignment(varlist, explist)
          StatFunctionCall(functioncall)
          StatDo(block)
          StatWhile(exp, block)
          StatRepeat(block, exp)
          StatIf(exp_block_pairs)
          StatForStep(name, exp_init, exp_end, exp_step, block)
          StatForIn(namelist, explist, block)
          StatFunction(funcname, funcbody)
          StatLocalFunction(funcname, funcbody)
          StatLocalAssignment(namelist, explist)
        """
        varlist = self._varlist()
        if varlist is not None:
            self._expect(lexer.TokSymbol('='))
            explist = self._explist
            if explist is None:
                raise ParserError('Expected expression in assignment',
                                  token=self._buf.peek())
            return StatAssignment(varlist, explist)

        functioncall = self._functioncall()
        if functioncall is not None:
            return StatFunctionCall(functioncall)

        do_tok = self._read(
        pass

    def _laststat(self):
        """Parse a laststat.

        laststat ::= return [explist] | break
        
        Returns:
          StatBreak()
          StatReturn(explist)
        """
        pass

    def _funcname(self):
        """Parse a funcname.

        funcname ::= Name {`.´ Name} [`:´ Name]

        Returns:
          FunctionName(namepath, methodname)
        """
        pass

    def _varlist(self):
        """Parse a varlist.

        varlist ::= var {`,´ var}

        Returns:
          VarList(vars)
        """
        pass

    def _var(self):
        """Parse a var.

        var ::=  Name | prefixexp `[´ exp `]´ | prefixexp `.´ Name

        Returns:
          VarName(name)
          VarIndex(exp_prefix, exp_index)
          VarAttribute(exp_prefix, attr_name)
        """
        pass

    def _namelist(self):
        """Parse a namelist.

        namelist ::= Name {`,´ Name}

        Returns:
          NameList(names)
        """
        pass

    def _explist(self):
        """Parse an explist.

        explist ::= {exp `,´} exp

        Returns:
          ExpList(exps)
        """
        pass

    def _exp(self):
        """Parse an exp.

        exp ::=  nil | false | true | Number | String | `...´ | function | 
		 prefixexp | tableconstructor | exp binop exp | unop exp

        Returns:
          ExpValue(value)
          ExpDots()
          ExpBinOp(exp1, binop, exp2)
          ExpUnOp(unop, exp)
        """
        pass
    
    def _prefixexp(self):
        """Parse a prefixexp.

        prefixexp ::= var | functioncall | `(´ exp `)´

        Returns:
          VarList(vars)
          VarName(name)
          VarIndex(exp_prefix, exp_index)
          VarAttribute(exp_prefix, attr_name)
          FunctionCall(exp_prefix, args)
          ExpValue(value)
          ExpDots()
          ExpBinOp(exp1, binop, exp2)
          ExpUnOp(unop, exp)
        """
        pass

    def _functioncall(self):
        """Parse a functioncall.

        functioncall ::=  prefixexp args | prefixexp `:´ Name args

        args ::=  `(´ [explist] `)´ | tableconstructor | String

        Returns:
          FunctionCall(exp_prefix, args)
        """
        pass
    
    def _function(self):
        """Parse a function.

        function ::= function funcbody

        Returns:
          Function(funcbody)
        """
        pass

    def _funcbody(self):
        """Parse a funcbody.

        funcbody ::= `(´ [parlist] `)´ block end

	parlist ::= namelist [`,´ `...´] | `...´

        Returns:
          FunctionBody(parlist, block)
        """
        pass

    def _tableconstructor(self):
        """Parse a tableconstructor.

        tableconstructor ::= `{´ [fieldlist] `}´

	fieldlist ::= field {fieldsep field} [fieldsep]

	fieldsep ::= `,´ | `;´

        Returns:
          TableConstructor(fields)
        """
        pass

    def _field(self):
        """Parse a field.

        field ::= `[´ exp `]´ `=´ exp | Name `=´ exp | exp

        Returns:
          FieldOtherThing(exp1, exp2)
          FieldNamed(name, exp)
          FieldExp(exp)
        """
        pass
        
    def process_tokens(self, tokens):
        """
        Args:
          tokens: An iterable of lexer.Token objects.

        Returns:
          The root Node of the AST.

        Raises:
          ParserError: Some pattern of tokens did not match the grammar.
        """
        self._buf = TokenBuffer(tokens)
        return self._chunk(TokenBuffer(tokens))
