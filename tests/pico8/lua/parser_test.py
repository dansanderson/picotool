#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lexer
from pico8.lua import parser


TOK_STREAM_SHORT = [lexer.TokNumber(v) for v in [1, 2, 3, 4, 5, 6, 7]]


class TestParser(unittest.TestCase):
    def testParserErrorMsg(self):
        # coverage
        txt = str(parser.ParserError(
            'msg', lexer.Token('x', lineno=1, charno=2)))


if __name__ == '__main__':
    unittest.main()
