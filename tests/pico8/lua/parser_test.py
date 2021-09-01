#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lexer
from pico8.lua import parser


LUA_SAMPLE = b'''
-- game of life: v1
-- by dddaaannn

alive_color = 7; width = 128; height = 128

board_i = 1
boards = {{}, {}}

cls()
for y=1,height do
  boards[1][y] = {}
  boards[2][y] = {}
  for x=1,width do
    boards[1][y][x] = 0
    boards[2][y][x] = 0
  end
end

-- draw an r pentomino
boards[1][60][64] = 1
boards[1][60][65] = 1
boards[1][61][63] = 1
boards[1][61][64] = 1
boards[1][62][64] = 1

function get(bi,x,y)
  if ((x < 1) or (x > width) or (y < 1) or (y > height)) then
    return 0
  end
  return boards[bi][y][x]
end

while true do
  for y=1,height do
    for x=1,width do
      pset(x-1,y-1,boards[board_i][y][x] * alive_color)
    end
  end
  flip()

  other_i = (board_i % 2) + 1
  for y=1,height do
    for x=1,width do
      neighbors = (
        get(board_i,x-1,y-1) +
        get(board_i,x,y-1) +
        get(board_i,x+1,y-1) +
        get(board_i,x-1,y) +
        get(board_i,x+1,y) +
        get(board_i,x-1,y+1) +
        get(board_i,x,y+1) +
        get(board_i,x+1,y+1))
      if ((neighbors == 3) or
          ((boards[board_i][y][x] == 1) and neighbors == 2)) then
        boards[other_i][y][x] = 1
      else
        boards[other_i][y][x] = 0
      end
    end
  end
  board_i = other_i
end
'''


def get_tokens(s):
    lxr = lexer.Lexer(version=4)
    lxr.process_lines([(l + b'\n') for l in s.split(b'\n')])
    return lxr.tokens


def get_parser(s):
    p = parser.Parser(version=4)
    p._tokens = get_tokens(s)
    p._pos = 0
    return p


class TestParser(unittest.TestCase):
    def testParserErrorMsg(self):
        # coverage
        txt = str(parser.ParserError(
            'msg', lexer.Token(b'x', lineno=1, charno=2)))

    def testCursorPeek(self):
        p = get_parser(b'break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertEqual(b'break', p._peek().value)
        self.assertEqual(0, p._pos)

    def testCursorAccept(self):
        p = get_parser(b'break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertIsNone(p._accept(lexer.TokName))
        self.assertIsNone(p._accept(lexer.TokKeyword(b'and')))
        self.assertIsNotNone(p._accept(lexer.TokKeyword(b'break')))
        self.assertEqual(1, p._pos)
        self.assertIsNotNone(p._accept(lexer.TokName))
        self.assertIsNotNone(p._accept(lexer.TokNumber))
        self.assertIsNotNone(p._accept(lexer.TokString))
        self.assertIsNotNone(p._accept(lexer.TokSymbol(b'==')))
        self.assertEqual(11, p._pos)

    def testCursorAcceptStopsAtMaxPos(self):
        p = get_parser(b'break name 7.42 -- Comment text\n"string literal" ==')
        p._max_pos = 4
        self.assertEqual(0, p._pos)
        self.assertIsNone(p._accept(lexer.TokName))
        self.assertIsNone(p._accept(lexer.TokKeyword(b'and')))
        self.assertIsNotNone(p._accept(lexer.TokKeyword(b'break')))
        self.assertEqual(1, p._pos)
        self.assertIsNotNone(p._accept(lexer.TokName))
        self.assertIsNone(p._accept(lexer.TokNumber))
        self.assertIsNone(p._accept(lexer.TokString))
        self.assertIsNone(p._accept(lexer.TokSymbol(b'==')))
        self.assertEqual(3, p._pos)

    def testCursorExpect(self):
        p = get_parser(b'break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertRaises(parser.ParserError,
                          p._expect, lexer.TokKeyword(b'and'))
        self.assertEqual(0, p._pos)
        tok_break = p._expect(lexer.TokKeyword(b'break'))
        self.assertEqual(b'break', tok_break.value)
        self.assertEqual(1, p._pos)
        tok_name = p._expect(lexer.TokName)
        self.assertEqual(b'name', tok_name.value)
        self.assertEqual(3, p._pos)  # "break, space, name"

    def testAssert(self):
        p = get_parser(b'break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual('DUMMY', p._assert('DUMMY', 'test assert'))
        try:
            p._assert(None, 'test assert')
            self.fail()
        except parser.ParserError as e:
            self.assertEqual('test assert', e.msg)
            self.assertEqual(b'break', e.token.value)

    def testNameListOneOK(self):
        p = get_parser(b'name1')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual(b'name1', node.names[0].value)
        self.assertEqual(1, len(node.names))

    def testNameListOneWithMoreOK(self):
        p = get_parser(b'name1 + name2')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual(b'name1', node.names[0].value)
        self.assertEqual(1, len(node.names))

    def testNameListMultipleOK(self):
        p = get_parser(b'name1,name2,   name3, name4')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual(9, p._pos)
        self.assertEqual(4, len(node.names))
        self.assertEqual(b'name1', node.names[0].value)
        self.assertEqual(b'name2', node.names[1].value)
        self.assertEqual(b'name3', node.names[2].value)
        self.assertEqual(b'name4', node.names[3].value)

    def testNameListErr(self):
        p = get_parser(b'123.45 name1')
        node = p._namelist()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testExpValueNil(self):
        p = get_parser(b'nil')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(None, node.value)

    def testExpValueFalse(self):
        p = get_parser(b'false')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(False, node.value)

    def testExpValueTrue(self):
        p = get_parser(b'true')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(True, node.value)

    def testExpValueNumber(self):
        p = get_parser(b'123.45')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertTrue(node.value.matches(lexer.TokNumber(b'123.45')))

    def testExpValueString(self):
        p = get_parser(b'"string literal"')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertTrue(node.value.matches(lexer.TokString(b'string literal')))

    def testExpValueDots(self):
        p = get_parser(b'...')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.VarargDots))

    def testExpValueErr(self):
        p = get_parser(b'break')
        node = p._exp()
        self.assertIsNone(node)

    def testExpUnOpHash(self):
        p = get_parser(b'#foo')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpUnOp))
        self.assertEqual(b'#', node.unop.value)
        self.assertTrue(isinstance(node.exp.value, parser.VarName))
        self.assertEqual(lexer.TokName(b'foo'), node.exp.value.name)

    def testExpUnOpMinus(self):
        p = get_parser(b'-45')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpUnOp))
        self.assertEqual(b'-', node.unop.value)
        self.assertTrue(isinstance(node.exp, parser.ExpValue))
        self.assertTrue(node.exp.value.matches(lexer.TokNumber(b'45')))

    def testExpUnOpAtPeek(self):
      p = get_parser(b'@0x5200')
      node = p._exp()
      self.assertIsNotNone(node)
      self.assertTrue(isinstance(node, parser.ExpUnOp))
      self.assertEqual(b'@', node.unop.value)
      self.assertTrue(isinstance(node.exp, parser.ExpValue))
      self.assertTrue(node.exp.value.matches(lexer.TokNumber(b'0x5200')))

    def testExpBinOp(self):
        p = get_parser(b'1 + 2')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)

    def testExpBinOpChain(self):
        p = get_parser(b'1 + 2 * 3 - 4 / 5..b^7 > 8 != foo')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(29, p._pos)
        self.assertEqual(b'foo', node.exp2.value.name.value)
        self.assertEqual(b'!=', node.binop.value)
        self.assertTrue(node.exp1.exp2.value.matches(lexer.TokNumber(b'8')))
        self.assertEqual(b'>', node.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp2.value.matches(lexer.TokNumber(b'7')))
        self.assertEqual(b'^', node.exp1.exp1.binop.value)
        self.assertEqual(b'b', node.exp1.exp1.exp1.exp2.value.name.value)
        self.assertEqual(b'..', node.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber(b'5')))
        self.assertEqual(b'/', node.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber(b'4')))
        self.assertEqual(b'-', node.exp1.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber(b'3')))
        self.assertEqual(b'*', node.exp1.exp1.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber(b'2')))
        self.assertEqual(b'+', node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.exp1.value.matches(lexer.TokNumber(b'1')))

    def testExpList(self):
        p = get_parser(b'1, 2, 3 - 4, a..b^7, foo')
        node = p._explist()
        self.assertIsNotNone(node)
        self.assertEqual(21, p._pos)
        self.assertEqual(5, len(node.exps))
        self.assertTrue(node.exps[0].value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.exps[1].value.matches(lexer.TokNumber(b'2')))
        self.assertTrue(node.exps[2].exp1.value.matches(lexer.TokNumber(b'3')))
        self.assertEqual(b'-', node.exps[2].binop.value)
        self.assertTrue(node.exps[2].exp2.value.matches(lexer.TokNumber(b'4')))
        self.assertEqual(b'a', node.exps[3].exp1.exp1.value.name.value)
        self.assertEqual(b'..', node.exps[3].exp1.binop.value)
        self.assertEqual(b'b', node.exps[3].exp1.exp2.value.name.value)
        self.assertEqual(b'^', node.exps[3].binop.value)
        self.assertTrue(node.exps[3].exp2.value.matches(lexer.TokNumber(b'7')))
        self.assertEqual(b'foo', node.exps[4].value.name.value)

    def testExpListErr(self):
        p = get_parser(b'break')
        node = p._explist()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testExpListIncompleteErr(self):
        p = get_parser(b'1, 2,')
        self.assertRaises(parser.ParserError,
                          p._explist)

    def testPrefixExpName(self):
        p = get_parser(b'foo')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)

    def testPrefixExpParenExp(self):
        p = get_parser(b'(2 + 3)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.ExpBinOp))
        self.assertTrue(node.exp1.value.matches(lexer.TokNumber(b'2')))
        self.assertEqual(b'+', node.binop.value)
        self.assertTrue(node.exp2.value.matches(lexer.TokNumber(b'3')))

    def testPrefixExpIndex(self):
        p = get_parser(b'foo[4 + 5]')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(8, p._pos)
        self.assertTrue(isinstance(node, parser.VarIndex))
        self.assertEqual(b'foo', node.exp_prefix.name.value)
        self.assertTrue(node.exp_index.exp1.value.matches(lexer.TokNumber(b'4')))
        self.assertEqual(b'+', node.exp_index.binop.value)
        self.assertTrue(node.exp_index.exp2.value.matches(lexer.TokNumber(b'5')))

    def testPrefixExpAttribute(self):
        p = get_parser(b'foo.bar')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.VarAttribute))
        self.assertEqual(b'foo', node.exp_prefix.name.value)
        self.assertEqual(b'bar', node.attr_name.value)

    def testPrefixExpChain(self):
        p = get_parser(b'(1+2)[foo].bar.baz')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertTrue(isinstance(node, parser.VarAttribute))
        self.assertEqual(b'baz', node.attr_name.value)
        self.assertTrue(isinstance(node.exp_prefix, parser.VarAttribute))
        self.assertEqual(b'bar', node.exp_prefix.attr_name.value)
        self.assertTrue(isinstance(node.exp_prefix.exp_prefix, parser.VarIndex))
        self.assertEqual(b'foo', node.exp_prefix.exp_prefix.exp_index.value.name.value)
        self.assertTrue(isinstance(node.exp_prefix.exp_prefix.exp_prefix, parser.ExpBinOp))
        self.assertTrue(node.exp_prefix.exp_prefix.exp_prefix.exp1.value.matches(lexer.TokNumber(b'1')))
        self.assertEqual(b'+', node.exp_prefix.exp_prefix.exp_prefix.binop.value)
        self.assertTrue(node.exp_prefix.exp_prefix.exp_prefix.exp2.value.matches(lexer.TokNumber(b'2')))

    def testFuncname(self):
        p = get_parser(b'foo')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual(b'foo', node.namepath[0].value)
        self.assertIsNone(node.methodname)

    def testFuncnameErr(self):
        p = get_parser(b'123')
        node = p._funcname()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testFuncnamePath(self):
        p = get_parser(b'foo.bar.baz')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual(b'foo', node.namepath[0].value)
        self.assertEqual(b'bar', node.namepath[1].value)
        self.assertEqual(b'baz', node.namepath[2].value)
        self.assertIsNone(node.methodname)

    def testFuncnameMethod(self):
        p = get_parser(b'foo:method')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual(b'foo', node.namepath[0].value)
        self.assertEqual(b'method', node.methodname.value)

    def testFuncnamePathAndMethod(self):
        p = get_parser(b'foo.bar.baz:method')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual(b'foo', node.namepath[0].value)
        self.assertEqual(b'bar', node.namepath[1].value)
        self.assertEqual(b'baz', node.namepath[2].value)
        self.assertEqual(b'method', node.methodname.value)

    def testArgsExpList(self):
        p = get_parser(b'(foo, bar, baz)')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(3, len(node.explist.exps))

    def testArgsString(self):
        p = get_parser(b'"string literal"')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(node.matches(lexer.TokString(b'string literal')))

    def testArgsNone(self):
        p = get_parser(b'')
        node = p._args()
        self.assertIsNone(node)

    def testPrefixExpFunctionCall(self):
        p = get_parser(b'fname(foo, bar, baz)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual(b'fname', node.exp_prefix.name.value)
        self.assertEqual(3, len(node.args.explist.exps))

    def testPrefixExpFunctionCallValueArgs(self):
        p = get_parser(b'fname(1, 2, 3)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)

    def testPrefixExpFunctionCallNoArgs(self):
        p = get_parser(b'fname()')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)

    def testPrefixExpFunctionCallMethod(self):
        p = get_parser(b'obj:method(foo, bar, baz)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual(b'obj', node.exp_prefix.name.value)
        self.assertEqual(b'method', node.methodname.value)
        self.assertEqual(3, len(node.args.explist.exps))

    def testFunctionCall(self):
        p = get_parser(b'fname(foo, bar, baz)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual(b'fname', node.exp_prefix.name.value)
        self.assertEqual(3, len(node.args.explist.exps))

    def testFunctionCallValueArgs(self):
        p = get_parser(b'foo(1, 2, 3)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)

    def testFunctionCallNoArgs(self):
        p = get_parser(b'foo()')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)

    def testFunctionCallMethod(self):
        p = get_parser(b'obj:method(foo, bar, baz)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual(b'obj', node.exp_prefix.name.value)
        self.assertEqual(b'method', node.methodname.value)
        self.assertEqual(3, len(node.args.explist.exps))

    def testFunctionCallErr(self):
        p = get_parser(b'foo + 7')
        node = p._functioncall()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testExpValuePrefixExp(self):
        p = get_parser(b'foo.bar')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node.value, parser.VarAttribute))
        self.assertEqual(b'foo', node.value.exp_prefix.name.value)
        self.assertEqual(b'bar', node.value.attr_name.value)

    def testFieldExpKey(self):
        p = get_parser(b'[1] = 2')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.FieldExpKey))
        self.assertTrue(node.key_exp.value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.exp.value.matches(lexer.TokNumber(b'2')))

    def testFieldNamedKey(self):
        p = get_parser(b'foo = 3')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertTrue(isinstance(node, parser.FieldNamedKey))
        self.assertEqual(b'foo', node.key_name.value)
        self.assertTrue(node.exp.value.matches(lexer.TokNumber(b'3')))

    def testFieldExp(self):
        p = get_parser(b'foo')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.FieldExp))
        self.assertEqual(b'foo', node.exp.value.name.value)

    def testTableConstructor(self):
        p = get_parser(b'{[1]=2,foo=3;4}')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertTrue(isinstance(node, parser.TableConstructor))
        self.assertEqual(3, len(node.fields))

        self.assertTrue(isinstance(node.fields[0], parser.FieldExpKey))
        self.assertTrue(node.fields[0].key_exp.value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.fields[0].exp.value.matches(lexer.TokNumber(b'2')))

        self.assertTrue(isinstance(node.fields[1], parser.FieldNamedKey))
        self.assertEqual(b'foo', node.fields[1].key_name.value)
        self.assertTrue(node.fields[1].exp.value.matches(lexer.TokNumber(b'3')))

        self.assertTrue(isinstance(node.fields[2], parser.FieldExp))
        self.assertTrue(node.fields[2].exp.value.matches(lexer.TokNumber(b'4')))

    def testTableConstructorTrailingSep(self):
        p = get_parser(b'{5,}')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.fields))
        self.assertTrue(node.fields[0].exp.value.matches(lexer.TokNumber(b'5')))

    def testTableConstructorEmpty(self):
        p = get_parser(b'{   }')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.TableConstructor))
        self.assertEqual([], node.fields)

    def testExpValueTableConstructor(self):
        p = get_parser(b'{5,}')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.value.fields))
        self.assertTrue(node.value.fields[0].exp.value.matches(lexer.TokNumber(b'5')))

    def testArgsTableConstructor(self):
        p = get_parser(b'{5,}')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.fields))
        self.assertTrue(node.fields[0].exp.value.matches(lexer.TokNumber(b'5')))

    def testFuncBodyEmptyParList(self):
        p = get_parser(b'() return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(6, p._pos)
        self.assertEqual(None, node.parlist)
        self.assertEqual(None, node.dots)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFuncBodyParList(self):
        p = get_parser(b'(foo, bar) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual(2, len(node.parlist.names))
        self.assertEqual(b'foo', node.parlist.names[0].value)
        self.assertEqual(b'bar', node.parlist.names[1].value)
        self.assertEqual(None, node.dots)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFuncBodyParListWithDots(self):
        p = get_parser(b'(foo, bar, ...) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertEqual(2, len(node.parlist.names))
        self.assertEqual(b'foo', node.parlist.names[0].value)
        self.assertEqual(b'bar', node.parlist.names[1].value)
        self.assertTrue(isinstance(node.dots, parser.VarargDots))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFuncBodyParListOnlyDots(self):
        p = get_parser(b'(...) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(None, node.parlist)
        self.assertTrue(isinstance(node.dots, parser.VarargDots))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFunctionNoArgs(self):
        p = get_parser(b'function() return end')
        node = p._function()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(None, node.funcbody.parlist)
        self.assertEqual(None, node.funcbody.dots)
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0],
                                   parser.StatReturn))

    def testFunctionFancyArgs(self):
        p = get_parser(b'function(foo, bar, ...) return end')
        node = p._function()
        self.assertIsNotNone(node)
        self.assertEqual(14, p._pos)
        self.assertEqual(2, len(node.funcbody.parlist.names))
        self.assertEqual(b'foo', node.funcbody.parlist.names[0].value)
        self.assertEqual(b'bar', node.funcbody.parlist.names[1].value)
        self.assertTrue(isinstance(node.funcbody.dots, parser.VarargDots))
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0],
                                   parser.StatReturn))

    def testExpValueFunction(self):
        p = get_parser(b'function() return end')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(None, node.value.funcbody.parlist)
        self.assertEqual(None, node.value.funcbody.dots)
        self.assertEqual(1, len(node.value.funcbody.block.stats))
        self.assertTrue(isinstance(node.value.funcbody.block.stats[0],
                                   parser.StatReturn))

    def testVarName(self):
        p = get_parser(b'foo')
        node = p._var()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertEqual(b'foo', node.name.value)

    def testVarIndex(self):
        p = get_parser(b'bar[7]')
        node = p._var()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(b'bar', node.exp_prefix.name.value)
        self.assertTrue(node.exp_index.value.matches(lexer.TokNumber(b'7')))

    def testVarAttribute(self):
        p = get_parser(b'baz.bat')
        node = p._var()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertEqual(b'baz', node.exp_prefix.name.value)
        self.assertEqual(b'bat', node.attr_name.value)

    def testVarList(self):
        p = get_parser(b'foo, bar[7], baz.bat')
        node = p._varlist()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual(3, len(node.vars))
        self.assertEqual(b'foo', node.vars[0].name.value)
        self.assertEqual(b'bar', node.vars[1].exp_prefix.name.value)
        self.assertTrue(node.vars[1].exp_index.value.matches(lexer.TokNumber(b'7')))
        self.assertEqual(b'baz', node.vars[2].exp_prefix.name.value)
        self.assertEqual(b'bat', node.vars[2].attr_name.value)

    def testLastStatBreak(self):
        p = get_parser(b'break')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.StatBreak))
        self.assertEqual(0, node._start_token_pos)
        self.assertEqual(1, node._end_token_pos)

    def testLastStatReturnNoExp(self):
        p = get_parser(b'return')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.StatReturn))
        self.assertIsNone(node.explist)

    def testLastStatReturnExps(self):
        p = get_parser(b'return 1, 2, 3')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertTrue(isinstance(node, parser.StatReturn))
        self.assertEqual(3, len(node.explist.exps))

    def testLastStatErr(self):
        p = get_parser(b'name')
        node = p._laststat()
        self.assertIsNone(node)

    def testStatAssignment(self):
        p = get_parser(b'foo, bar, baz = 1, 2, 3')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(17, p._pos)
        self.assertEqual(3, len(node.varlist.vars))
        self.assertEqual(b'foo', node.varlist.vars[0].name.value)
        self.assertEqual(b'bar', node.varlist.vars[1].name.value)
        self.assertEqual(b'baz', node.varlist.vars[2].name.value)
        self.assertTrue(node.assignop.matches(lexer.TokSymbol(b'=')))
        self.assertEqual(3, len(node.explist.exps))
        self.assertTrue(node.explist.exps[0].value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.explist.exps[1].value.matches(lexer.TokNumber(b'2')))
        self.assertTrue(node.explist.exps[2].value.matches(lexer.TokNumber(b'3')))

    def testStatFunctionCall(self):
        p = get_parser(b'foo(1, 2, 3)')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual(b'foo', node.functioncall.exp_prefix.name.value)
        self.assertEqual(3, len(node.functioncall.args.explist.exps))
        self.assertTrue(node.functioncall.args.explist.exps[0].value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.functioncall.args.explist.exps[1].value.matches(lexer.TokNumber(b'2')))
        self.assertTrue(node.functioncall.args.explist.exps[2].value.matches(lexer.TokNumber(b'3')))

    def testStatDo(self):
        p = get_parser(b'do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))

    def testStatWhile(self):
        p = get_parser(b'while true do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(True, node.exp.value)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))

    def testStatWhileLiveExample(self):
        p = get_parser(b'\t\twhile(s.y<b.y)do\n'
                       b'\t\t\ts.y+=1;e.y+=1;s.x+=dx1;e.x+=dx2;\n'
                       b'\t\t\tline(s.x,s.y,e.x,e.y);\n'
                       b'\t\tend\n')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(62, p._pos)
        self.assertEqual(5, len(node.block.stats))

    def testStatRepeat(self):
        p = get_parser(b'repeat break until true')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))
        self.assertEqual(True, node.exp.value)

    def testStatIf(self):
        p = get_parser(b'if true then break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))

    def testStatIfElse(self):
        p = get_parser(b'if true then break else return end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertEqual(2, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertIsNone(node.exp_block_pairs[1][0])
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatReturn))
        self.assertIsNone(node.exp_block_pairs[1][1].stats[0].explist)

    def testStatIfElseIf(self):
        p = get_parser(b'if true then break elseif false then return end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(17, p._pos)
        self.assertEqual(2, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertEqual(False, node.exp_block_pairs[1][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatReturn))
        self.assertIsNone(node.exp_block_pairs[1][1].stats[0].explist)

    def testStatIfElseIfElse(self):
        p = get_parser(b'if true then break elseif false then break else return end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(21, p._pos)
        self.assertEqual(3, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertEqual(False, node.exp_block_pairs[1][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatBreak))
        self.assertIsNone(node.exp_block_pairs[2][0])
        self.assertTrue(isinstance(node.exp_block_pairs[2][1].stats[0], parser.StatReturn))
        self.assertIsNone(node.exp_block_pairs[2][1].stats[0].explist)

    def testStatIfShort(self):
        p = get_parser(b'if (true) break\nreturn')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))

    def testStatIfShortEOF(self):
        p = get_parser(b'if (true) break')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))

    def testStatIfShortElse(self):
        p = get_parser(b'if (true) break else break\nreturn')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(11, p._pos)
        self.assertEqual(2, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertIsNone(node.exp_block_pairs[1][0])
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatBreak))

    def testStatIfShortEmptyElse(self):
        p = get_parser(b'if (true) break else  \nreturn')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))

    def testStatIfDoHack(self):
        p = get_parser(b'if (true) do\nbreak end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(11, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value.value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))

    def testStatFor(self):
        p = get_parser(b'for foo=1,3 do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertEqual(b'foo', node.name.value)
        self.assertTrue(node.exp_init.value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.exp_end.value.matches(lexer.TokNumber(b'3')))
        self.assertIsNone(node.exp_step)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))

    def testStatForStep(self):
        p = get_parser(b'for foo=1,3,10 do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(15, p._pos)
        self.assertEqual(b'foo', node.name.value)
        self.assertTrue(node.exp_init.value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.exp_end.value.matches(lexer.TokNumber(b'3')))
        self.assertTrue(node.exp_step.value.matches(lexer.TokNumber(b'10')))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))

    def testStatForIn(self):
        p = get_parser(b'for foo, bar in 1, 3 do\n  break\nend\n')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(20, p._pos)
        self.assertEqual(2, len(node.namelist.names))
        self.assertEqual(b'foo', node.namelist.names[0].value)
        self.assertEqual(b'bar', node.namelist.names[1].value)
        self.assertEqual(2, len(node.explist.exps))
        self.assertTrue(node.explist.exps[0].value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.explist.exps[1].value.matches(lexer.TokNumber(b'3')))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))

    def testStatFunction(self):
        p = get_parser(b'function foo(a, b, c) break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(16, p._pos)
        self.assertEqual(1, len(node.funcname.namepath))
        self.assertEqual(b'foo', node.funcname.namepath[0].value)
        self.assertIsNone(node.funcname.methodname)
        self.assertEqual(3, len(node.funcbody.parlist.names))
        self.assertEqual(b'a', node.funcbody.parlist.names[0].value)
        self.assertEqual(b'b', node.funcbody.parlist.names[1].value)
        self.assertEqual(b'c', node.funcbody.parlist.names[2].value)
        self.assertIsNone(node.funcbody.dots)
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0], parser.StatBreak))

    def testStatLocalFunction(self):
        p = get_parser(b'local function foo(a, b, c) break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(18, p._pos)
        self.assertEqual(b'foo', node.funcname.value)
        self.assertEqual(3, len(node.funcbody.parlist.names))
        self.assertEqual(b'a', node.funcbody.parlist.names[0].value)
        self.assertEqual(b'b', node.funcbody.parlist.names[1].value)
        self.assertEqual(b'c', node.funcbody.parlist.names[2].value)
        self.assertIsNone(node.funcbody.dots)
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0], parser.StatBreak))

    def testStatLocalAssignment(self):
        p = get_parser(b'local foo, bar, baz')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(3, len(node.namelist.names))
        self.assertEqual(b'foo', node.namelist.names[0].value)
        self.assertEqual(b'bar', node.namelist.names[1].value)
        self.assertEqual(b'baz', node.namelist.names[2].value)
        self.assertIsNone(node.explist)

    def testStatLocalAssignmentWithValues(self):
        p = get_parser(b'local foo, bar, baz = 1, 2, 3')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(19, p._pos)
        self.assertEqual(3, len(node.namelist.names))
        self.assertEqual(b'foo', node.namelist.names[0].value)
        self.assertEqual(b'bar', node.namelist.names[1].value)
        self.assertEqual(b'baz', node.namelist.names[2].value)
        self.assertEqual(3, len(node.explist.exps))
        self.assertTrue(node.explist.exps[0].value.matches(lexer.TokNumber(b'1')))
        self.assertTrue(node.explist.exps[1].value.matches(lexer.TokNumber(b'2')))
        self.assertTrue(node.explist.exps[2].value.matches(lexer.TokNumber(b'3')))

    def testStatGoto(self):
        p = get_parser(b'goto foobar')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertEqual(b'foobar', node.label)

    def testStatLabel(self):
        p = get_parser(b'::foobar::')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertEqual(b'foobar', node.label)

    def testStatAssignmentAnonymousFunctionTable(self):
        p = get_parser(b'''
player =
{
    init=function(this)
        print(t1)
    end,
    update=function(this)
        print(t2)
    end,
    draw=function(this)
        print(t3)
    end
}
''')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(61, p._pos)
        self.assertEqual(1, len(node.varlist.vars))
        self.assertEqual(b'player', node.varlist.vars[0].name.value)
        self.assertTrue(node.assignop.matches(lexer.TokSymbol(b'=')))
        self.assertEqual(1, len(node.explist.exps))
        self.assertEqual(3, len(node.explist.exps[0].value.fields))
        self.assertEqual(b'init', node.explist.exps[0].value.fields[0].key_name.value)
        self.assertTrue(isinstance(node.explist.exps[0].value.fields[0].exp.value, parser.Function))
        self.assertEqual(b'update', node.explist.exps[0].value.fields[1].key_name.value)
        self.assertTrue(isinstance(node.explist.exps[0].value.fields[1].exp.value, parser.Function))
        self.assertEqual(b'draw', node.explist.exps[0].value.fields[2].key_name.value)
        self.assertTrue(isinstance(node.explist.exps[0].value.fields[2].exp.value, parser.Function))

    def testChunk(self):
        p = get_parser(LUA_SAMPLE)
        node = p._chunk()
        self.assertIsNotNone(node)
        self.assertEqual(626, p._pos)
        self.assertEqual(14, len(node.stats))

    def testChunkExtraSemis(self):
        p = get_parser(b' ; ; foo=1; bar=1; ;\n;baz=3; \n;  ;')
        node = p._chunk()
        self.assertIsNotNone(node)
        self.assertEqual(27, p._pos)
        self.assertEqual(3, len(node.stats))

    def testProcessTokens(self):
        tokens = get_tokens(LUA_SAMPLE)
        p = parser.Parser(version=4)
        p.process_tokens(tokens)
        self.assertIsNotNone(p.root)
        self.assertEqual(14, len(p.root.stats))

    # TODO: Poor newline handling means the parser tokens aren't identical to the input tokens! Fix?
    #def testTokensOnAST(self):
    #    tokens = get_tokens(b' return')
    #    p = parser.Parser(version=4)
    #    p.process_tokens(tokens)
    #    parser_tokens = list(p.tokens)
    #    self.assertEqual(parser_tokens, tokens)


if __name__ == '__main__':
    unittest.main()
