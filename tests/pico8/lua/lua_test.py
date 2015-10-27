#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lua


VALID_LUA_SHORT_LINES = [
    '-- short test\n',
    '-- by dan\n',
    'function foo()\n',
    '  return 999\n',
    'end\n'
]


class TestLua(unittest.TestCase):
    def testInit(self):
        result = lua.Lua(4)
        self.assertEqual(4, result._lexer._version)
        self.assertEqual(4, result._parser._version)
        
    def testFromLines(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        self.assertEqual(17, len(result._lexer._tokens))

    def testGetCharCount(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        self.assertEqual(sum(len(l) for l in VALID_LUA_SHORT_LINES),
                         result.get_char_count())

    def testGetTokenCount(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        self.assertEqual(7, result.get_token_count())

    def testGetTitle(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        self.assertEqual('short test', result.get_title())

    def testGetByline(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        self.assertEqual('by dan', result.get_byline())

    def testBaseLuaWriterNotYetImplemented(self):
        # coverage
        self.assertRaises(NotImplementedError,
                          lua.BaseLuaWriter(None, None).to_lines)

        
class TestLuaEchoWriter(unittest.TestCase):
    def testToLinesEchoWriter(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        lines = list(result.to_lines())
        self.assertEqual(lines, VALID_LUA_SHORT_LINES)
        
    def testToLinesEchoWriterLastCharIsntNewline(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES + ['break'], 4)
        lines = list(result.to_lines())
        self.assertEqual(lines, VALID_LUA_SHORT_LINES + ['break'])


class TestLuaASTEchoWriter(unittest.TestCase):
    def testToLinesASTEchoWriter(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaASTEchoWriter))
        self.assertEqual(lines, VALID_LUA_SHORT_LINES)

        
if __name__ == '__main__':
    unittest.main()
