"""The Lua parser."""

from .. import util
from . import lexer


__all__ = [
    'Parser',
    'ParserError',
    'Node',
    'Chunk',
    'StatAssignment',
    'StatFunctionCall',
    'StatDo',
    'StatWhile',
    'StatRepeat',
    'StatIf',
    'StatForStep',
    'StatForIn',
    'StatFunction',
    'StatLocalFunction',
    'StatLocalAssignment',
    'StatGoto',
    'StatLabel',
    'StatBreak',
    'StatReturn',
    'FunctionName',
    'FunctionArgs',
    'VarList',
    'VarName',
    'VarIndex',
    'VarAttribute',
    'NameList',
    'ExpList',
    'ExpValue',
    'VarargDots',
    'ExpBinOp',
    'ExpUnOp',
    'FunctionCall',
    'FunctionCallMethod',
    'Function',
    'FunctionBody',
    'TableConstructor',
    'FieldOtherThing',
    'FieldNamed',
    'FieldExp',
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
            self.msg, self.token._lineno + 1, self.token._charno)


class Node():
    """A base class for all AST nodes."""

    @property
    def start_pos(self):
        return self._start_token_pos

    @property
    def end_pos(self):
        return self._end_token_pos


# These are all Node subclasses that initialize members with
# (required) positional arguments. They are created and added to the
# module's namespace in the loop below the list.
_ast_node_types = (
    ('Chunk', ('stats',)),
    ('StatAssignment', ('varlist', 'assignop', 'explist')),
    ('StatFunctionCall', ('functioncall',)),
    ('StatDo', ('block',)),
    ('StatWhile', ('exp', 'block')),
    ('StatRepeat', ('block', 'exp')),
    ('StatIf', ('exp_block_pairs',)),
    ('StatForStep', ('name', 'exp_init', 'exp_end', 'exp_step', 'block')),
    ('StatForIn', ('namelist', 'explist', 'block')),
    ('StatFunction', ('funcname', 'funcbody')),

    # StatLocalFunction funcname is a TokName, not a FunctionName
    ('StatLocalFunction', ('funcname', 'funcbody')),

    ('StatLocalAssignment', ('namelist', 'explist')),
    ('StatGoto', ('label',)),
    ('StatLabel', ('label',)),
    ('StatBreak', ()),
    ('StatReturn', ('explist',)),
    ('FunctionName', ('namepath', 'methodname')),
    ('FunctionArgs', ('explist',)),
    ('VarList', ('vars',)),
    ('VarName', ('name',)),
    ('VarIndex', ('exp_prefix', 'exp_index')),
    ('VarAttribute', ('exp_prefix', 'attr_name')),
    ('NameList', ('names',)),
    ('ExpList', ('exps',)),

    # TODO: rewrite expression parsing so that the AST captures associativity.
    # (See _exp_binop). Right now, all binary operators chain right to left:
    # 1 + 2 - 3 => ExpBinOp(ExpBinOp(1, +, 2), -, 3)
    #
    # value: None, False, True, TokNumber, TokString, Function,
    #   TableConstructor, Var*, FunctionCall, Exp*
    ('ExpValue', ('value',)),
    ('VarargDots', ()),
    ('ExpBinOp', ('exp1', 'binop', 'exp2')),
    ('ExpUnOp', ('unop', 'exp')),

    # args: None, ExpList, TableConstructor, str
    ('FunctionCall', ('exp_prefix', 'args')),
    ('FunctionCallMethod', ('exp_prefix', 'methodname', 'args')),

    ('Function', ('funcbody',)),
    ('FunctionBody', ('parlist', 'dots', 'block')),
    ('TableConstructor', ('fields',)),
    ('FieldExpKey', ('key_exp', 'exp')),
    ('FieldNamedKey', ('key_name', 'exp')),
    ('FieldExp', ('exp',)),
)
for (name, fields) in _ast_node_types:
    def node_init(self, *args, **kwargs):
        self._start_token_pos = kwargs.get('start')
        self._end_token_pos = kwargs.get('end')
        if 'start' in kwargs:
            del kwargs['start']
        if 'end' in kwargs:
            del kwargs['end']
        if len(args) != len(self._fields):
            raise TypeError(
                'Initializer for {} requires {} fields, saw {}'.format(
                    self._name, len(self._fields), len(args)))
        for i in range(len(self._fields)):
            setattr(self, self._fields[i], args[i])
        for k in kwargs:
            setattr(self, k, kwargs[k])
    cls = type(name, (Node,), {'__init__': node_init,
                               '_name': name, '_fields': fields})
    globals()[name] = cls


# (!= is PICO-8 specific.)
BINOP_PATS = ([lexer.TokSymbol(sym) for sym in [
    '<', '>', '<=', '>=', '~=', '!=', '==', '..', '+', '-', '*', '/', '%', '^'
]] + [lexer.TokKeyword('and'), lexer.TokKeyword('or')])

    
    
class Parser():
    """The parser."""

    def __init__(self, version):
        """Initializer.

        Args:
          version: The Pico-8 data version from the game file header.
        """
        self._version = version
        self._tokens = None
        self._pos = None
        self._ast = None

        # If _max_pos is not None, _accept will not advance the cursor beyond
        # it and will return None for any action that would.
        self._max_pos = None
        
    def _peek(self):
        """Return the token under the cursor.

        Returns:
          The token under the cursor, or None if there is no next token.
        """
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _accept(self, tok_pattern):
        """Match the token under the cursor, and advance the cursor if matched.

        If tok_pattern is not TokSpace, TokNewline, or TokComment,
        this method consumes all whitespace, newline, and comment
        tokens prior to the matched token, and returns them with the
        token. If the first non-space token does not match, the cursor
        returns to where it was before the call.

        If self._max_pos is not None, then the cursor is not allowed
        to advance past that position. If consuming whitespace and the
        accepted token would leave the cursor past this point, the
        cursor is rewound to the beginning and the method returns
        None. This mechanism is exclusively for supporting short-if.

        Args:
          tok_pattern: The lexer.Token subclass or subclass instance
            to match. If tok is a subclass, the current token matches
            if it has the same subclass. If tok is an instance, the
            current token matches if it has the same subclass and
            equal data.

        Returns:
          If the token under the cursor matches, returns the token. Otherwise
          None.

        """
        start_pos = self._pos

        # Find the first non-space token (unless accepting a space).
        while True:
            cur_tok = self._peek()
            if (cur_tok is None or
                cur_tok.matches(tok_pattern) or
                (not isinstance(cur_tok, lexer.TokSpace) and
                 not isinstance(cur_tok, lexer.TokNewline) and
                 not isinstance(cur_tok, lexer.TokComment))):
                break
            self._pos += 1
        
        if (cur_tok is not None and
            cur_tok.matches(tok_pattern) and
            (self._max_pos is None or self._pos < self._max_pos)):
            self._pos += 1
            return cur_tok

        self._pos = start_pos
        return None

    def _expect(self, tok_pattern):
        """Accepts a token, or raises a ParserError if not found.

        Args:
          tok_pattern: The lexer.Token subclass or subclass instance
            to match, as described by TokenBuffer.accept().

        Returns:
          The token under the cursor if it matches, otherwise None.

        Raises:
          ParserError: The pattern doesn't match the next token.
        """
        tok = self._accept(tok_pattern)
        if tok is not None:
            return tok
        if isinstance(tok_pattern, type):
            name = getattr(tok_pattern, 'name', tok_pattern.__name__)
            raise ParserError('Expected {}'.format(name),
                              token=self._peek())
        raise ParserError('Expected {}'.format(tok_pattern._data),
                          token=self._peek())

    def _assert(self, node_or_none, desc):
        """Asserts that a node parsed, or raises a ParserError.

        Args:
          node_or_none: The result of a parsing function.

        Returns:
          The node, if not None.

        Raises:
          ParserError: The node is None.
        """
        if node_or_none is not None:
            return node_or_none
        raise ParserError(desc, token=self._peek())

    def _chunk(self):
        """Parse a chunk / block.
        
        chunk :: = {stat [';']} [laststat [';']]

        Returns:
          Chunk(stats)
        """
        pos = self._pos
        stats = []
        while True:
            # Eat leading and intervening semicolons.
            while self._accept(lexer.TokSymbol(';')) is not None:
                pass
            stat = self._stat()
            if stat is None:
                break
            stats.append(stat)

        # Eat leading and intervening semicolons.
        while self._accept(lexer.TokSymbol(';')) is not None:
            pass
        
        laststat = self._laststat()
        if laststat is not None:
            stats.append(laststat)

        # Eat trailing semicolons.
        while self._accept(lexer.TokSymbol(';')) is not None:
            pass
        
        return Chunk(stats, start=pos, end=self._pos)

    def _stat(self):
        """Parse a stat.

        stat ::=  varlist '=' explist | 
		 functioncall | 
		 do block end | 
		 while exp do block end | 
		 repeat block until exp | 
		 if exp then block {elseif exp then block} [else block] end | 
		 for Name '=' exp ',' exp [',' exp] do block end | 
		 for namelist in explist do block end | 
		 function funcname funcbody | 
		 local function Name funcbody | 
		 local namelist ['=' explist] |
                 ::label::

        Returns:
          StatAssignment(varlist, assignop, explist)
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
          StatGoto(label)
          StatLabel(label)
        """
        pos = self._pos
        
        varlist = self._varlist()
        if varlist is not None:
            # (Missing '=' is not a fatal error because varlist might also match
            # the beginning of a functioncall.)
            assign_op = (self._accept(lexer.TokSymbol('=')) or
                         self._accept(lexer.TokSymbol('+=')) or
                         self._accept(lexer.TokSymbol('-=')) or
                         self._accept(lexer.TokSymbol('*=')) or
                         self._accept(lexer.TokSymbol('/=')) or
                         self._accept(lexer.TokSymbol('%=')))
            if assign_op is not None:
                explist = self._assert(self._explist(),
                                       'Expected expression in assignment')
                return StatAssignment(varlist, assign_op, explist,
                                      start=pos, end=self._pos)
        self._pos = pos
        
        functioncall = self._functioncall()
        if functioncall is not None:
            return StatFunctionCall(functioncall, start=pos, end=self._pos)
        self._pos = pos

        if self._accept(lexer.TokKeyword('do')) is not None:
            block = self._assert(self._chunk(), 'block in do')
            self._expect(lexer.TokKeyword('end'))
            return StatDo(block, start=pos, end=self._pos)

        if self._accept(lexer.TokKeyword('while')) is not None:
            exp = self._assert(self._exp(), 'exp in while')
            self._expect(lexer.TokKeyword('do'))
            block = self._assert(self._chunk(), 'block in while')
            self._expect(lexer.TokKeyword('end'))
            return StatWhile(exp, block, start=pos, end=self._pos)

        if self._accept(lexer.TokKeyword('repeat')) is not None:
            block = self._assert(self._chunk(),
                                 'block in repeat')
            self._expect(lexer.TokKeyword('until'))
            exp = self._assert(self._exp(),
                               'expression in repeat')
            return StatRepeat(block, exp, start=pos, end=self._pos)

        if self._accept(lexer.TokKeyword('if')) is not None:
            exp_block_pairs = []
            exp = self._exp()

            then_pos = self._pos
            if (self._accept(lexer.TokKeyword('then')) is None and
                (self._tokens[exp._end_token_pos - 1] == lexer.TokSymbol(')'))):
                # Check for Pico-8 short form.

                then_end_pos = exp._end_token_pos
                while (then_end_pos < len(self._tokens) and
                       not self._tokens[then_end_pos].matches(lexer.TokNewline)):
                    then_end_pos += 1
                    
                try:
                    self._max_pos = then_end_pos
                    block = self._assert(self._chunk(),
                                         'valid chunk in short-if')
                    else_block = None
                    if self._accept(lexer.TokKeyword('else')) is not None:
                        # Pico-8 accepts an else with nothing after it.
                        else_block = self._chunk()
                finally:
                    self._max_pos = None
                    
                # (Use exp.value here to unwrap the condition from the
                # bracketed expression.)
                exp_block_pairs = [(exp.value, block)]
                if else_block is not None and len(else_block.stats) > 0:
                    exp_block_pairs.append((None, else_block))
                return StatIf(exp_block_pairs, start=pos, end=self._pos,
                              short_if=True)
            
            self._pos = then_pos

            # TODO: hack: accept "do" for "then" to support seven carts that
            # exploit a loophole in short-if.
            self._expect(lexer.TokKeyword('then'))
            block = self._chunk()
            self._assert(block, 'Expected block in if')
            exp_block_pairs.append((exp, block))
            while self._accept(lexer.TokKeyword('elseif')) is not None:
                exp = self._exp()
                self._expect(lexer.TokKeyword('then'))
                block = self._chunk()
                self._assert(block, 'Expected block in elseif')
                exp_block_pairs.append((exp, block))
            if self._accept(lexer.TokKeyword('else')) is not None:
                block = self._chunk()
                self._assert(block, 'Expected block in else')
                exp_block_pairs.append((None, block))
            self._expect(lexer.TokKeyword('end'))
            return StatIf(exp_block_pairs, start=pos, end=self._pos)

        if self._accept(lexer.TokKeyword('for')) is not None:
            for_pos = self._pos

            name = self._accept(lexer.TokName)
            eq_sym = self._accept(lexer.TokSymbol('='))
            if eq_sym is not None:
                exp_init = self._assert(self._exp(), 'exp-init in for')
                self._expect(lexer.TokSymbol(','))
                exp_end = self._assert(self._exp(), 'exp-end in for')
                exp_step = None
                if self._accept(lexer.TokSymbol(',')):
                    exp_step = self._assert(self._exp(), 'exp-step in for')
                self._expect(lexer.TokKeyword('do'))
                block = self._assert(self._chunk(), 'block in for')
                self._expect(lexer.TokKeyword('end'))
                return StatForStep(name, exp_init, exp_end, exp_step, block,
                                   start=pos, end=self._pos)
            self._pos = for_pos
                
            namelist = self._assert(self._namelist(), 'namelist in for-in')
            self._expect(lexer.TokKeyword('in'))
            explist = self._assert(self._explist(), 'explist in for-in')
            self._expect(lexer.TokKeyword('do'))
            block = self._assert(self._chunk(), 'block in for-in')
            self._expect(lexer.TokKeyword('end'))
            return StatForIn(namelist, explist, block, start=pos, end=self._pos)

        if self._accept(lexer.TokKeyword('function')) is not None:
            funcname = self._assert(self._funcname(), 'funcname in function')
            funcbody = self._assert(self._funcbody(), 'funcbody in function')
            return StatFunction(funcname, funcbody, start=pos, end=self._pos)

        if self._accept(lexer.TokKeyword('local')) is not None:
            if self._accept(lexer.TokKeyword('function')) is not None:
                funcname = self._expect(lexer.TokName)
                funcbody = self._assert(self._funcbody(),
                                        'funcbody in local function')
                return StatLocalFunction(funcname, funcbody,
                                         start=pos, end=self._pos)
            namelist = self._assert(self._namelist(),
                                    'namelist in local assignment')
            explist = None
            if self._accept(lexer.TokSymbol('=')) is not None:
                explist = self._assert(self._explist(),
                                       'explist in local assignment')
            return StatLocalAssignment(namelist, explist,
                                       start=pos, end=self._pos)

        if self._accept(lexer.TokKeyword('goto')) is not None:
            label = self._expect(lexer.TokName)
            return StatGoto(label.value, start=pos, end=self._pos)
        
        label = self._accept(lexer.TokLabel)
        if label is not None:
            # Remove colons from label.
            label_name = label.value[2:-2]
            return StatLabel(label_name, start=pos, end=self._pos)
        
        self._pos = pos
        return None
        
    def _laststat(self):
        """Parse a laststat.

        laststat ::= return [explist] | break
        
        Returns:
          StatBreak()
          StatReturn(explist)
        """
        pos = self._pos
        if self._accept(lexer.TokKeyword('break')) is not None:
            return StatBreak(start=pos, end=self._pos)
        if self._accept(lexer.TokKeyword('return')) is not None:
            explist = self._explist()
            return StatReturn(explist, start=pos, end=self._pos)
        self._pos = pos
        return None

    def _funcname(self):
        """Parse a funcname.

        funcname ::= Name {'.' Name} [':' Name]

        Returns:
          FunctionName(namepath, methodname)
        """
        pos = self._pos
        namepath = []
        methodname = None
        
        name = self._accept(lexer.TokName)
        if name is None:
            return None
        namepath.append(name)
        while self._accept(lexer.TokSymbol('.')) is not None:
            namepath.append(self._expect(lexer.TokName))
        if self._accept(lexer.TokSymbol(':')) is not None:
            methodname = self._expect(lexer.TokName)

        return FunctionName(namepath, methodname, start=pos, end=self._pos)

    def _varlist(self):
        """Parse a varlist.

        varlist ::= var {',' var}

        Returns:
          VarList(vars)
        """
        pos = self._pos
        _vars = []
        var = self._var()
        if var is None:
            return None
        _vars.append(var)
        while self._accept(lexer.TokSymbol(',')) is not None:
            _vars.append(self._assert(self._var(), 'var in varlist'))
        return VarList(_vars, start=pos, end=self._pos)

    def _var(self):
        """Parse a var.

        var ::=  Name | prefixexp '[' exp ']' | prefixexp '.' Name

        Returns:
          VarName(name)
          VarIndex(exp_prefix, exp_index)
          VarAttribute(exp_prefix, attr_name)
        """
        exp_prefix = self._prefixexp()
        if (isinstance(exp_prefix, VarName) or
            isinstance(exp_prefix, VarAttribute) or
            isinstance(exp_prefix, VarIndex)):
            return exp_prefix
        return None

    def _namelist(self):
        """Parse a namelist.

        namelist ::= Name {',' Name}

        Returns:
          NameList(names)
        """
        pos = self._pos
        names = []
        name = self._accept(lexer.TokName)
        if name is None:
            return None
        names.append(name)
        last_pos = self._pos
        while self._accept(lexer.TokSymbol(',')) is not None:
            name = self._accept(lexer.TokName)
            if name is None:
                # Don't eat the trailing separator if there is one.
                self._pos = last_pos
                break
            names.append(name)
            last_pos = self._pos
            
        return NameList(names, start=pos, end=self._pos)

    def _explist(self):
        """Parse an explist.

        explist ::= {exp ','} exp

        Returns:
          ExpList(exps)
        """
        pos = self._pos
        exps = []
        exp = self._exp()
        if exp is None:
            self._pos = pos
            return None
        exps.append(exp)
        while True:
            if self._accept(lexer.TokSymbol(',')) is None:
                break
            exp = self._assert(self._exp(), 'exp after comma')
            exps.append(exp)
        if len(exps) == 0:
            self._pos = pos
            return None
        return ExpList(exps, start=pos, end=self._pos)

    def _exp(self):
        """Parse an exp.

        exp ::= exp_term exp_binop

        Returns:
          ExpValue(value)
          VarargDots()
          ExpUnOp(unop, exp)
          ExpBinOp(exp1, binop, exp2)
        """
        pos = self._pos
        exp_term = self._exp_term()
        if exp_term is None:
            return None
        return self._exp_binop(exp_term)

    def _exp_binop(self, exp_first):
        """Parse the recursive part of a binary-op expression.

        exp_binop ::= binop exp_term exp_binop | <empty>

        Args:
          exp_first: The already-made first argument to the operator.

        Returns:
          ExpBinOp(exp_first, binop, exp_term, exp_binop)
          exp_first
        """
        pos = self._pos

        # TODO: rewrite binary expression parsing so that the AST captures
        # associativity:
        #   or
        #   and
        #   < > <= >= ~= != ==
        #   .. (right associative)
        #   + -
        #   * / %
        #   not # - (unary)
        #   ^ (right associative)

        for pat in BINOP_PATS:
            binop = self._accept(pat)
            if binop is not None:
                exp_second = self._assert(self._exp_term(), 'exp2 in binop')
                this_binop = ExpBinOp(exp_first, binop, exp_second,
                                      start=pos, end=self._pos)
                return self._exp_binop(this_binop)

        self._pos = pos
        return exp_first
        
    def _exp_term(self):
        """Parse a non-recursive expression term.

        exp_term ::=  nil | false | true | Number | String | '...' | function | 
                      prefixexp | tableconstructor | unop exp

        Returns:
          ExpValue(value)
          VarargDots()
          ExpUnOp(unop, exp)
        """
        pos = self._pos
        if self._accept(lexer.TokKeyword('nil')) is not None:
            return ExpValue(None, start=pos, end=self._pos)
        if self._accept(lexer.TokKeyword('false')) is not None:
            return ExpValue(False, start=pos, end=self._pos)
        if self._accept(lexer.TokKeyword('true')) is not None:
            return ExpValue(True, start=pos, end=self._pos)
        val = self._accept(lexer.TokNumber)
        if val is not None:
            return ExpValue(val, start=pos, end=self._pos)
        val = self._accept(lexer.TokString)
        if val is not None:
            return ExpValue(val, start=pos, end=self._pos)
        if self._accept(lexer.TokSymbol('...')) is not None:
            return VarargDots(start=pos, end=self._pos)
        val = self._function()
        if val is not None:
            return ExpValue(val, start=pos, end=self._pos)
        val = self._prefixexp()
        if val is not None:
            return ExpValue(val, start=pos, end=self._pos)
        val = self._tableconstructor()
        if val is not None:
            return ExpValue(val, start=pos, end=self._pos)
        
        unop = self._accept(lexer.TokSymbol('-'))
        if unop is None:
            unop = self._accept(lexer.TokKeyword('not'))
            if unop is None:
                unop = self._accept(lexer.TokSymbol('#'))
                if unop is None:
                    return None
        exp = self._assert(self._exp(), 'exp after unary op')
        return ExpUnOp(unop, exp, start=pos, end=self._pos)
    
    def _prefixexp(self):
        """Parse a prefixexp.

        prefixexp ::= var | functioncall | '(' exp ')'

        functioncall ::=  prefixexp args | prefixexp ':' Name args

        args ::=  '(' [explist] ')' | tableconstructor | String

        This expands to:

        prefixexp ::= Name | prefixexp '[' exp ']' | prefixexp '.' Name |
                      prefixexp args | prefixexp ':' Name args | '(' exp ')'

        Or:

        prefixexp ::= Name prefixexp_recur |
                      '(' exp ')' prefixexp_recur

        Returns:
          VarList(vars)
          VarName(name)
          VarIndex(exp_prefix, exp_index)
          VarAttribute(exp_prefix, attr_name)
          FunctionCall(exp_prefix, args)
          FunctionCallMethod(exp_prefix, methodname, args)
          ExpValue(value)
          VarargDots()
          ExpBinOp(exp1, binop, exp2)
          ExpUnOp(unop, exp)
        """
        pos = self._pos
        name = self._accept(lexer.TokName)
        if name is not None:
            return self._prefixexp_recur(
                VarName(name, start=pos, end=self._pos))
        
        if self._accept(lexer.TokSymbol('(')) is not None:
            # (exp can be None.)
            exp = self._exp()
            self._expect(lexer.TokSymbol(')'))
            return self._prefixexp_recur(exp)

        return None

    def _prefixexp_recur(self, prefixexp_first):
        """Parse the recurring part of a prefixexp.

        prefixexp_recur ::= '[' exp ']' prefixexp_recur |   # VarIndex
                            '.' Name prefixexp_recur |      # VarAttribute
                            args prefixexp_recur |          # FunctionCall
                            ':' Name args prefixexp_recur | # FunctionCallMethod
                            <empty>

        Args:
          prefixexp_first: The first part of the prefixexp.

        Returns:
          VarIndex(exp_prefix, exp_index)
          VarAttribute(exp_prefix, attr_name)
          FunctionCall(exp_prefix, args)
          FunctionCallMethod(exp_prefix, methodname, args)
          prefixexp_first
        """
        pos = self._pos
        if self._accept(lexer.TokSymbol('[')) is not None:
            exp = self._assert(self._exp(), 'exp in prefixexp index')
            self._expect(lexer.TokSymbol(']'))
            return self._prefixexp_recur(VarIndex(prefixexp_first, exp,
                                                  start=pos, end=self._pos))
        if self._accept(lexer.TokSymbol('.')) is not None:
            name = self._expect(lexer.TokName)
            return self._prefixexp_recur(VarAttribute(prefixexp_first, name,
                                                      start=pos, end=self._pos))
        args = self._args()
        if args is not None:
            return self._prefixexp_recur(FunctionCall(prefixexp_first, args,
                                                      start=pos, end=self._pos))
        if self._accept(lexer.TokSymbol(':')) is not None:
            name = self._expect(lexer.TokName)
            args = self._assert(self._args(), 'args for method call')
            return self._prefixexp_recur(
                FunctionCallMethod(prefixexp_first, name, args,
                                   start=pos, end=self._pos))
        return prefixexp_first
    
    def _functioncall(self):
        """Parse a functioncall.

        Returns:
          FunctionCall(exp_prefix, args)
          FunctionCallMethod(exp_prefix, methodname, args)
        """
        pos = self._pos

        full_exp = self._prefixexp()
        if (full_exp is None or
            (not isinstance(full_exp, FunctionCall) and
             not isinstance(full_exp, FunctionCallMethod))):
            self._pos = pos
            return None
        return full_exp

    def _args(self):
        """Parse functioncall args.

        Returns:
          ExpList(exps)
          TableConstructor(fields)
          lexer.TokString
          None
        """
        pos = self._pos
        if self._accept(lexer.TokSymbol('(')):
            explist = self._explist()
            self._expect(lexer.TokSymbol(')'))
            return FunctionArgs(explist, start=pos, end=self._pos)

        tableconstructor = self._tableconstructor()
        if tableconstructor is not None:
            return tableconstructor
        
        string_lit = self._accept(lexer.TokString)
        if string_lit is not None:
            return string_lit
        
        return None
        
    def _function(self):
        """Parse a function.

        function ::= function funcbody

        Returns:
          Function(funcbody)
        """
        pos = self._pos
        if self._accept(lexer.TokKeyword('function')):
            funcbody = self._assert(self._funcbody(), 'funcbody in function')
            return Function(funcbody, start=pos, end=self._pos)
        return None

    def _funcbody(self):
        """Parse a funcbody.

        funcbody ::= '(' [parlist] ')' block end

	parlist ::= namelist [',' '...'] | '...'

        Returns:
          FunctionBody(parlist, dots, block)
        """
        pos = self._pos
        if self._accept(lexer.TokSymbol('(')) is None:
            return None

        namelist = self._namelist()
        dots = None
        if namelist is not None:
            if self._accept(lexer.TokSymbol(',')) is not None:
                dots_pos = self._pos
                dots = self._expect(lexer.TokSymbol('...'))
        else:
            dots_pos = self._pos
            dots = self._accept(lexer.TokSymbol('...'))
        if dots is not None:
            dots = VarargDots(start=dots_pos, end=self._pos)

        self._expect(lexer.TokSymbol(')'))
        block = self._assert(self._chunk(), 'block in funcbody')
        self._expect(lexer.TokKeyword('end'))
            
        return FunctionBody(namelist, dots, block, start=pos, end=self._pos)

    def _tableconstructor(self):
        """Parse a tableconstructor.

        tableconstructor ::= '{' [fieldlist] '}'

	fieldlist ::= field {fieldsep field} [fieldsep]

	fieldsep ::= ',' | ';'

        Returns:
          TableConstructor(fields)
        """
        pos = self._pos
        if self._accept(lexer.TokSymbol('{')) is None:
            return None

        fields = []
        field = self._field()
        if field is not None:
            fields.append(field)
        while (self._accept(lexer.TokSymbol(',')) is not None or
               self._accept(lexer.TokSymbol(';')) is not None):
            field = self._field()
            if field is None:
                break
            fields.append(field)

        self._expect(lexer.TokSymbol('}'))
        return TableConstructor(fields, start=pos, end=self._pos)

    def _field(self):
        """Parse a field.

        field ::= '[' exp ']' '=' exp | Name '=' exp | exp

        Returns:
          FieldExpKey(key_exp, exp)
          FieldNamedKey(key_name, exp)
          FieldExp(exp)
        """
        pos = self._pos
        if self._accept(lexer.TokSymbol('[')):
            key_exp = self._assert(self._exp(), 'exp key in field')
            self._expect(lexer.TokSymbol(']'))
            self._expect(lexer.TokSymbol('='))
            exp = self._assert(self._exp(), 'exp value in field')
            return FieldExpKey(key_exp, exp, start=pos, end=self._pos)

        key_name = self._accept(lexer.TokName)
        if (key_name is not None and
            self._accept(lexer.TokSymbol('=')) is not None):
            exp = self._assert(self._exp(), 'exp value in field')
            return FieldNamedKey(key_name, exp, start=pos, end=self._pos)
        self._pos = pos
        
        exp = self._exp()
        if exp is not None:
            return FieldExp(exp, start=pos, end=self._pos)

        return None
        
    def process_tokens(self, tokens):
        """Process a list of tokens into an AST.

        This method must be single-threaded. To process multiple
        tokens in multiple threads, use one Parser instance per
        thread.

        Args:
          tokens: An iterable of lexer.Token objects. All tokens will
            be loaded into memory for processing.

        Raises:
          ParserError: Some pattern of tokens did not match the grammar.
        """
        self._tokens = list(tokens)
        self._pos = 0
        self._ast = self._assert(self._chunk(), 'input to be a program')

    @property
    def root(self):
        """The root of the AST produced by process_tokens()."""
        return self._ast
