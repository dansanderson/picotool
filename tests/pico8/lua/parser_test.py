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
