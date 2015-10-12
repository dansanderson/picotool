#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lexer
from pico8.lua import parser


def get_parser(s):
    lxr = lexer.Lexer(version=4)
    lxr.process_lines([(l + '\n') for l in s.split('\n')])
    p = parser.Parser(version=4)
    p._tokens = lxr.tokens
    p._pos = 0
    return p
    

class TestParser(unittest.TestCase):
    def testParserErrorMsg(self):
        # coverage
        txt = str(parser.ParserError(
            'msg', lexer.Token('x', lineno=1, charno=2)))

    def testCursorPeek(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertEqual('break', p._peek()._data)
        self.assertEqual(0, p._pos)

    def testCursorAccept(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertIsNone(p._accept(lexer.TokName))
        self.assertIsNone(p._accept(lexer.TokKeyword('and')))
        self.assertIsNotNone(p._accept(lexer.TokKeyword('break')))
        self.assertEqual(1, p._pos)
        self.assertIsNotNone(p._accept(lexer.TokName))
        self.assertIsNotNone(p._accept(lexer.TokNumber))
        self.assertIsNotNone(p._accept(lexer.TokString))
        self.assertIsNotNone(p._accept(lexer.TokSymbol('==')))
        self.assertEqual(11, p._pos)

    def testCursorExpect(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertRaises(parser.ParserError,
                          p._expect, lexer.TokKeyword('and'))
        self.assertEqual(0, p._pos)
        tok_break = p._expect(lexer.TokKeyword('break'))
        self.assertEqual('break', tok_break._data)
        self.assertEqual(1, p._pos)
        tok_name = p._expect(lexer.TokName)
        self.assertEqual('name', tok_name._data)
        self.assertEqual(3, p._pos)  # "break, space, name"

    def testAssert(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual('DUMMY', p._assert('DUMMY', 'test assert'))
        try:
            p._assert(None, 'test assert')
            self.fail()
        except parser.ParserError as e:
            self.assertEqual('test assert', e.msg)
            self.assertEqual('break', e.token._data)

    def testNameListOneOK(self):
        p = get_parser('name1')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual('name1', node.names[0]._data)
        self.assertEqual(1, len(node.names))

    def testNameListOneWithMoreOK(self):
        p = get_parser('name1 + name2')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual('name1', node.names[0]._data)
        self.assertEqual(1, len(node.names))

    def testNameListMultipleOK(self):
        p = get_parser('name1,name2,   name3, name4')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual(9, p._pos)
        self.assertEqual(4, len(node.names))
        self.assertEqual('name1', node.names[0]._data)
        self.assertEqual('name2', node.names[1]._data)
        self.assertEqual('name3', node.names[2]._data)
        self.assertEqual('name4', node.names[3]._data)
        
    def testNameListErr(self):
        p = get_parser('123.45 name1')
        node = p._namelist()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)
    
    def testExpValueNil(self):
        p = get_parser('nil')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(None, node.value)

    def testExpValueFalse(self):
        p = get_parser('false')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(False, node.value)

    def testExpValueTrue(self):
        p = get_parser('true')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(True, node.value)

    def testExpValueNumber(self):
        p = get_parser('123.45')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual('123.45', node.value)
        
    def testExpValueString(self):
        p = get_parser('"string literal"')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual('string literal', node.value)
        
    def testExpValueDots(self):
        p = get_parser('...')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.VarargDots))

    def testExpValueErr(self):
        p = get_parser('break')
        node = p._exp()
        self.assertIsNone(node)

    def testExpUnOpHash(self):
        p = get_parser('#foo')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpUnOp))
        self.assertEqual('#', node.unop._data)
        self.assertTrue(isinstance(node.exp.value, parser.VarName))
        self.assertEqual(lexer.TokName('foo'), node.exp.value.name)

    def testExpUnOpMinus(self):
        p = get_parser('-45')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpUnOp))
        self.assertEqual('-', node.unop._data)
        self.assertTrue(isinstance(node.exp, parser.ExpValue))
        self.assertEqual('45', node.exp.value)

    def testExpBinOp(self):
        p = get_parser('1 + 2')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        
    def testExpBinOpChain(self):
        p = get_parser('1 + 2 * 3 - 4 / 5..6^7 > 8 != foo')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(29, p._pos)
        self.assertEqual('foo', node.exp2.value.name._data)
        self.assertEqual('!=', node.binop._data)
        self.assertEqual('8', node.exp1.exp2.value)
        self.assertEqual('>', node.exp1.binop._data)
        self.assertEqual('7', node.exp1.exp1.exp2.value)
        self.assertEqual('^', node.exp1.exp1.binop._data)
        self.assertEqual('6', node.exp1.exp1.exp1.exp2.value)
        self.assertEqual('..', node.exp1.exp1.exp1.binop._data)
        self.assertEqual('5', node.exp1.exp1.exp1.exp1.exp2.value)
        self.assertEqual('/', node.exp1.exp1.exp1.exp1.binop._data)
        self.assertEqual('4', node.exp1.exp1.exp1.exp1.exp1.exp2.value)
        self.assertEqual('-', node.exp1.exp1.exp1.exp1.exp1.binop._data)
        self.assertEqual('3', node.exp1.exp1.exp1.exp1.exp1.exp1.exp2.value)
        self.assertEqual('*', node.exp1.exp1.exp1.exp1.exp1.exp1.binop._data)
        self.assertEqual('2', node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.exp2.value)
        self.assertEqual('+', node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.binop._data)
        self.assertEqual('1', node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.exp1.value)

    def testExpList(self):
        p = get_parser('1, 2, 3 - 4, 5..6^7, foo')
        node = p._explist()
        self.assertIsNotNone(node)
        self.assertEqual(21, p._pos)
        self.assertEqual(5, len(node.exps))
        self.assertEqual('1', node.exps[0].value)
        self.assertEqual('2', node.exps[1].value)
        self.assertEqual('3', node.exps[2].exp1.value)
        self.assertEqual('-', node.exps[2].binop._data)
        self.assertEqual('4', node.exps[2].exp2.value)
        self.assertEqual('5', node.exps[3].exp1.exp1.value)
        self.assertEqual('..', node.exps[3].exp1.binop._data)
        self.assertEqual('6', node.exps[3].exp1.exp2.value)
        self.assertEqual('^', node.exps[3].binop._data)
        self.assertEqual('7', node.exps[3].exp2.value)
        self.assertEqual('foo', node.exps[4].value.name._data)

    def testExpListErr(self):
        p = get_parser('break')
        node = p._explist()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testExpListIncompleteErr(self):
        p = get_parser('1, 2,')
        self.assertRaises(parser.ParserError,
                          p._explist)

    def testPrefixExpName(self):
        p = get_parser('foo')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        
    def testPrefixExpParenExp(self):
        p = get_parser('(2 + 3)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.ExpBinOp))
        self.assertEqual('2', node.exp1.value)
        self.assertEqual('+', node.binop._data)
        self.assertEqual('3', node.exp2.value)
        
    def testPrefixExpIndex(self):
        p = get_parser('foo[4 + 5]')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(8, p._pos)
        self.assertTrue(isinstance(node, parser.VarIndex))
        self.assertEqual('foo', node.exp_prefix.name._data)
        self.assertEqual('4', node.exp_index.exp1.value)
        self.assertEqual('+', node.exp_index.binop._data)
        self.assertEqual('5', node.exp_index.exp2.value)
        
    def testPrefixExpAttribute(self):
        p = get_parser('foo.bar')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.VarAttribute))
        self.assertEqual('foo', node.exp_prefix.name._data)
        self.assertEqual('bar', node.attr_name._data)

    def testPrefixExpChain(self):
        p = get_parser('(1+2)[foo].bar.baz')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertTrue(isinstance(node, parser.VarAttribute))
        self.assertEqual('baz', node.attr_name._data)
        self.assertTrue(isinstance(node.exp_prefix, parser.VarAttribute))
        self.assertEqual('bar', node.exp_prefix.attr_name._data)
        self.assertTrue(isinstance(node.exp_prefix.exp_prefix, parser.VarIndex))
        self.assertEqual('foo', node.exp_prefix.exp_prefix.exp_index.value.name._data)
        self.assertTrue(isinstance(node.exp_prefix.exp_prefix.exp_prefix, parser.ExpBinOp))
        self.assertEqual('1', node.exp_prefix.exp_prefix.exp_prefix.exp1.value)
        self.assertEqual('+', node.exp_prefix.exp_prefix.exp_prefix.binop._data)
        self.assertEqual('2', node.exp_prefix.exp_prefix.exp_prefix.exp2.value)

    def testFuncname(self):
        p = get_parser('foo')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0]._data)
        self.assertIsNone(node.methodname)

    def testFuncnameErr(self):
        p = get_parser('123')
        node = p._funcname()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)
        
    def testFuncnamePath(self):
        p = get_parser('foo.bar.baz')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0]._data)
        self.assertEqual('bar', node.namepath[1]._data)
        self.assertEqual('baz', node.namepath[2]._data)
        self.assertIsNone(node.methodname)
        
    def testFuncnameMethod(self):
        p = get_parser('foo:method')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0]._data)
        self.assertEqual('method', node.methodname._data)

    def testFuncnamePathAndMethod(self):
        p = get_parser('foo.bar.baz:method')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0]._data)
        self.assertEqual('bar', node.namepath[1]._data)
        self.assertEqual('baz', node.namepath[2]._data)
        self.assertEqual('method', node.methodname._data)
    
    def testArgsExpList(self):
        p = get_parser('(foo, bar, baz)')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(3, len(node.exps))
        
    def testArgsString(self):
        p = get_parser('"string literal"')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertEqual('string literal', node)
    
    def testArgsNone(self):
        p = get_parser('')
        node = p._args()
        self.assertIsNone(node)
    
    def testPrefixExpFunctionCall(self):
        p = get_parser('fname(foo, bar, baz)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual('fname', node.exp_prefix.name._data)
        self.assertEqual(3, len(node.args.exps))
        
    def testPrefixExpFunctionCallMethod(self):
        p = get_parser('obj:method(foo, bar, baz)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual('obj', node.exp_prefix.name._data)
        self.assertEqual('method', node.methodname._data)
        self.assertEqual(3, len(node.args.exps))
        
    def testFunctionCall(self):
        p = get_parser('fname(foo, bar, baz)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual('fname', node.exp_prefix.name._data)
        self.assertEqual(3, len(node.args.exps))

    def testFunctionCallMethod(self):
        p = get_parser('obj:method(foo, bar, baz)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual('obj', node.exp_prefix.name._data)
        self.assertEqual('method', node.methodname._data)
        self.assertEqual(3, len(node.args.exps))

    def testFunctionCallErr(self):
        p = get_parser('foo + 7')
        node = p._functioncall()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testExpValuePrefixExp(self):
        p = get_parser('foo.bar')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node.value, parser.VarAttribute))
        self.assertEqual('foo', node.value.exp_prefix.name._data)
        self.assertEqual('bar', node.value.attr_name._data)
    
    def testFieldExpKey(self):
        p = get_parser('[1] = 2')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.FieldExpKey))
        self.assertEqual('1', node.key_exp.value)
        self.assertEqual('2', node.exp.value)
        
    def testFieldNamedKey(self):
        p = get_parser('foo = 3')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertTrue(isinstance(node, parser.FieldNamedKey))
        self.assertEqual('foo', node.key_name._data)
        self.assertEqual('3', node.exp.value)
        
    def testFieldExp(self):
        p = get_parser('foo')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.FieldExp))
        self.assertEqual('foo', node.exp.value.name._data)
        
    def testTableConstructor(self):
        p = get_parser('{[1]=2,foo=3;4}')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertTrue(isinstance(node, parser.TableConstructor))
        self.assertEqual(3, len(node.fields))

        self.assertTrue(isinstance(node.fields[0], parser.FieldExpKey))
        self.assertEqual('1', node.fields[0].key_exp.value)
        self.assertEqual('2', node.fields[0].exp.value)

        self.assertTrue(isinstance(node.fields[1], parser.FieldNamedKey))
        self.assertEqual('foo', node.fields[1].key_name._data)
        self.assertEqual('3', node.fields[1].exp.value)

        self.assertTrue(isinstance(node.fields[2], parser.FieldExp))
        self.assertEqual('4', node.fields[2].exp.value)

    def testTableConstructorTrailingSep(self):
        p = get_parser('{5,}')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.fields))
        self.assertEqual('5', node.fields[0].exp.value)

    def testTableConstructorEmpty(self):
        p = get_parser('{   }')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.TableConstructor))
        self.assertEqual([], node.fields)
        
    def testExpValueTableConstructor(self):
        p = get_parser('{5,}')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.value.fields))
        self.assertEqual('5', node.value.fields[0].exp.value)
        
    def testArgsTableConstructor(self):
        p = get_parser('{5,}')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.fields))
        self.assertEqual('5', node.fields[0].exp.value)

    def testFuncBodyEmptyParList(self):
        p = get_parser('() return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(6, p._pos)
        # TODO: parlist, dots, block

    def testFuncBodyParList(self):
        p = get_parser('(foo, bar) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        # TODO: parlist, dots, block

    def testFuncBodyParListWithDots(self):
        p = get_parser('(foo, bar, ...) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        # TODO: parlist, dots, block

    def testFuncBodyParListOnlyDots(self):
        p = get_parser('(...) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        # TODO: parlist, dots, block

    #def testFunction(self):
    #    pass
    #def testExpValueFunction(self):
    #    pass
    #def testVar(self):
    #    pass
    #def testVarList(self):
    #    pass

    def testLastStatBreak(self):
        p = get_parser('break')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.StatBreak))
        self.assertEqual(0, node._start_token_pos)
        self.assertEqual(1, node._end_token_pos)

    def testLastStatReturnNoExp(self):
        p = get_parser('return')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.StatReturn))
        self.assertEqual(0, len(node.explist))

    def testLastStatReturnExps(self):
        p = get_parser('return 1, 2, 3')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertTrue(isinstance(node, parser.StatReturn))
        self.assertEqual(3, len(node.explist))
        # TODO: exps

    def testLastStatErr(self):
        p = get_parser('name')
        node = p._laststat()
        self.assertIsNone(node)

    #def testStat(self):
    #    pass
    #def testChunk(self):
    #    pass
    #def testProcessTokens(self):
    #    pass

if __name__ == '__main__':
    unittest.main()
