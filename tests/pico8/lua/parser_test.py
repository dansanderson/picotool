#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lexer
from pico8.lua import parser


TOK_STREAM_SHORT = [lexer.TokNumber(v) for v in [1, 2, 3, 4, 5, 6, 7]]


class TestTokenBuffer(unittest.TestCase):
    def testReadsStream(self):
        buf = parser.TokenBuffer(iter(TOK_STREAM_SHORT))
        for i in range(7):
            t = buf.peek()
            self.assertIsNotNone(t)
            self.assertTrue(t.matches(lexer.TokNumber(i+1)))
            self.assertIsNone(buf.accept(lexer.TokKeyword('break')))
            self.assertIsNotNone(buf.accept(lexer.TokNumber(i+1)))
        self.assertIsNone(buf.peek())
        self.assertIsNone(buf.accept(lexer.TokNumber))

    def testRewindAndAdvance(self):
        buf = parser.TokenBuffer(iter(TOK_STREAM_SHORT))
        for i in range(3):
            self.assertIsNotNone(buf.accept(lexer.TokNumber(i+1)))
        buf.rewind()
        for i in range(3):
            self.assertIsNotNone(buf.accept(lexer.TokNumber(i+1)))
        buf.advance()
        for i in range(3):
            self.assertIsNotNone(buf.accept(lexer.TokNumber(i+4)))
        buf.rewind()
        for i in range(3):
            self.assertIsNotNone(buf.accept(lexer.TokNumber(i+4)))
        

class TestParser(unittest.TestCase):
    def testParserErrorMsg(self):
        # coverage
        txt = str(parser.ParserError(
            'msg', lexer.Token('x', lineno=1, charno=2)))


if __name__ == '__main__':
    unittest.main()
