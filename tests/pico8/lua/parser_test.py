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


if __name__ == '__main__':
    unittest.main()
