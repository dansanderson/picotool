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
        
    #def testExpValueFunction(self):
    #    pass
    #def testExpValuePrefixExp(self):
    #    pass
    #def testExpValueTableConstructor(self):
    #    pass
    #def testExpUnOp(self):
    #    pass
    #def testExpBinOp(self):
    #    pass
    #def testExpBinOpChain(self):
    #    pass

    #def testExpList(self):
    #    pass
    #def testPrefixExp(self):
    #    pass
    
    #def testFieldExpKey(self):
    #    pass
    #def testFieldNamedKey(self):
    #    pass
    #def testFieldExp(self):
    #    pass
    #def testTableConstructor(self):
    #    pass
    #def testFuncBody(self):
    #    pass
    #def testFunction(self):
    #    pass
    #def testArgs(self):
    #    pass
    #def testFunctionCall(self):
    #    pass
    #def testVar(self):
    #    pass
    #def testVarList(self):
    #    pass
    #def testFuncname(self):
    #    pass

    def testLastStatOK(self):
        p = get_parser('break')
        node = p._laststat()
        self.assertTrue(isinstance(node, parser.StatBreak))
        self.assertEqual(0, node._start_token_pos)
        self.assertEqual(1, node._end_token_pos)
        
    def testLastStatErr(self):
        p = get_parser('name')
        node = p._laststat()
        self.assertIsNone(node)

    #def testStat(self):
    #    pass
    #def testChunk(self):
    #    pass


if __name__ == '__main__':
    unittest.main()
