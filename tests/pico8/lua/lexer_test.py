#!/usr/bin/env python3

import io
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lexer


VALID_P8_HEADER = '''pico-8 cartridge // http://www.pico-8.com
version 4
'''

INVALID_P8_HEADER = '''INVALID HEADER
INVALID HEADER
'''

VALID_P8_LUA_SECTION_HEADER = '__lua__\n'

VALID_P8_FOOTER = (
    '\n__gfx__\n' + (('0' * 128) + '\n') * 128 +
    '__gff__\n' + (('0' * 256) + '\n') * 2 +
    '__map__\n' + (('0' * 256) + '\n') * 32 +
    '__sfx__\n' + '0001' + ('0' * 164) + '\n' +
    ('001' + ('0' * 165) + '\n') * 63 +
    '__music__\n' + '00 41424344\n' * 64 + '\n\n')

VALID_LUA = '''
v1 = nil
v2 = false
v3 = true
v4 = 123
v5 = 123.45
v6 = "string"
v7 = 7 < 10
v8 = -12
v9 = not false

func()
v10 = func(1, v3, "string")

v11 = { "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday",
        "Sunday" }
v12 = v11[3]

v13 = {}
v13.x = 100
v13.y = 200
v13["z"] = 300

do
 func()
 v2 = not v3
end

-- Comment
-- do
--  func()
--  v2 = not v3

counter = 10  -- end of line comment
while counter > 0 do
 counter -= 1
 if counter % 2 == 0 then
  func()
 end
 if func(counter) > 900 then
  break
 end
end

repeat
 counter += 1
 if counter % 2 == 0 then
  func()
 end
until counter == 10

if v4 > 0 then
 func(1)
elseif v5 and (v4 < 0) then
 func(-2)
elseif v4 < 0 then
 func(-1)
else
 func(0)
end

for x = 1,10,2 do
 func(x)
 if x % 2 == 0 then
  func(x+1)
 end
end

for x,y,z in foobar do
 func(x)
 if x % 2 == 0 then
  func(x+1)
 end
end

function func(x, y, z)
 local foobar = 999
 if x % 2 == 0 then
  func(x+1)
 end
 return 111
end

local function func2(x, y, z)
 if x % 2 == 0 then
  func(x+1)
 end
end

a = {"hello", "blah"}
add(a, "world")
del(a, "blah")
print(count(a)) -- 2

for item in all(a) do print(item) end
foreach(a, print)
foreach(a, function(i) print(i) end)

x = 1 y = 2 print(x+y) -- this line will run ok

-- Pico-8 shorthand
if (not b) i=1 j=2
a += 2
a -= 2
a *= 2
a /= 2
a %= 2
if (a != 2) print("ok") end
if (a ~= 2) print("ok") end

'''


class TestLexer(unittest.TestCase):
    def testTokenLength(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('break')
        self.assertEqual(1, len(lxr._tokens))
        self.assertEqual(5, len(lxr._tokens[0]))

    def testTokenRepr(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('break')
        self.assertEqual(1, len(lxr._tokens))
        self.assertIn('line 0', repr(lxr._tokens[0]))
        
    def testTokenMatches(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('break')
        self.assertEqual(1, len(lxr._tokens))
        self.assertTrue(lxr._tokens[0].matches(lexer.TokKeyword('break')))
        self.assertTrue(lxr._tokens[0].matches(lexer.TokKeyword))
        self.assertFalse(lxr._tokens[0].matches(lexer.TokKeyword('and')))
        self.assertFalse(lxr._tokens[0].matches(lexer.TokSpace))
        
    def testWhitespace(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('    \n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(4, len(lxr._tokens[0]))

    def testOneKeyword(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('and\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokKeyword('and'), lxr._tokens[0])

    def testOneName(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('android\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokName('android'), lxr._tokens[0])

    def testThreeDots(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('...\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokSymbol('...'), lxr._tokens[0])

    def testStringDoubleQuotes(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('"abc def ghi and jkl"\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokString('abc def ghi and jkl'),
                         lxr._tokens[0])

    def testStringSingleQuotes(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line("'abc def ghi and jkl'\n")
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokString('abc def ghi and jkl'),
                         lxr._tokens[0])

    # TODO: confirm the correct multi-line string behavior
    def testStringMultipleLines(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('"abc def ghi \n')
        lxr._process_line('and jkl"\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokString('abc def ghi \nand jkl'),
                         lxr._tokens[0])
        
    def testStringMultipleLinesPlusAToken(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('"abc def ghi \nand jkl" and\n')
        self.assertEqual(4, len(lxr._tokens))
        self.assertEqual(lexer.TokString('abc def ghi \nand jkl'),
                         lxr._tokens[0])
        self.assertEqual(lexer.TokKeyword('and'), lxr._tokens[2])

    def testStringEscapes(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('"\\\n\\a\\b\\f\\n\\r\\t\\v\\\\\\"\\\'\\65"\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokString('\n\a\b\f\n\r\t\v\\"\'A'),
                         lxr._tokens[0])

    def testComment(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('-- comment text and stuff\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokComment('-- comment text and stuff'),
                         lxr._tokens[0])
        
    def testTokenAndComment(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('and-- comment text and stuff\n')
        self.assertEqual(3, len(lxr._tokens))
        self.assertEqual(lexer.TokKeyword('and'),
                         lxr._tokens[0])
        self.assertEqual(lexer.TokComment('-- comment text and stuff'),
                         lxr._tokens[1])
        
    def testNumberInteger(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('1234567890\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokNumber('1234567890'),
                         lxr._tokens[0])

    def testNumberDecimal(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('1.234567890\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokNumber('1.234567890'),
                         lxr._tokens[0])

    def testNumberDecimalWithExp(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('1.234567890e-6\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokNumber('1.234567890e-6'),
                         lxr._tokens[0])
        
    def testNegatedNumber(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('-1.234567890e-6\n')
        self.assertEqual(3, len(lxr._tokens))
        self.assertEqual(lexer.TokSymbol('-'),
                         lxr._tokens[0])
        self.assertEqual(lexer.TokNumber('1.234567890e-6'),
                         lxr._tokens[1])

    def testNumberHex(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('0x1234567890abcdef\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokNumber('0x1234567890abcdef'),
                         lxr._tokens[0])

    def testNumberHexWithFrac(self):
        lxr = lexer.Lexer(version=4)
        lxr._process_line('0x1234567890abcdef.1bbf\n')
        self.assertEqual(2, len(lxr._tokens))
        self.assertEqual(lexer.TokNumber('0x1234567890abcdef.1bbf'),
                         lxr._tokens[0])

    def testValidLuaNoErrors(self):
        lxr = lexer.Lexer(version=4)
        for line in VALID_LUA.split('\n'):
            lxr._process_line(line)
        # TODO: test samples of tokens

    def testLexerError(self):
        lxr = lexer.Lexer(version=4)
        try:
            lxr._process_line('123 @ 456')
            self.fail()
        except lexer.LexerError as e:
            txt = str(e)  # coverage test
            self.assertEqual(1, e.lineno)
            self.assertEqual(5, e.charno)

    def testProcessLines(self):
        lxr = lexer.Lexer(version=4)
        lxr.process_lines([
            'function foo()\n',
            '  return 999\n',
            'end\n'
        ])
        self.assertEqual(13, len(lxr._tokens))

    def testTokensProperty(self):
        lxr = lexer.Lexer(version=4)
        lxr.process_lines([
            'function foo()\n',
            '  return 999\n',
            'end\n'
        ])
        self.assertEqual(13, len(lxr.tokens))

        
if __name__ == '__main__':
    unittest.main()
