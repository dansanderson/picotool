#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lua


VALID_LUA_SHORT_LINES = [l + b'\n' for l in b'''-- short test
-- by dan
function foo()
  return 999
end'''.split(b'\n')]


VALID_LUA_EVERY_NODE = [l + b'\n' for l in b'''
-- the code with the nodes
-- doesn't have to make sense

function f(arg1, ...)
  local t = {}
  t[arg1] = 999
  t['extra'] = ...
  return t
end

local function myprint(msg)
  print(msg)
end

a = 1
f(a, a+1 , a + 2 )
beta, gamma = 2, 3

do
  gamma = 4
  break
end

while a < 10 do
  -- increase a
  a += 1
  if a % 2 == 0 then
    f(a)
  elseif a > 5 then
    f(a, 5)
  else
    f(a, 1)
    beta *= 2
  end
end

repeat
  -- reduce a
  a -= 1
  f(a)
until a <= 0

for a=3, 10, 2 do
    f(a)
end

for beta in vals() do
      f(beta)
end

if a < 20 then
  goto mylabel
end
a = -20 + 2 - .1
gamma = 9.999e-3
::mylabel::

if (a * 10 > 100) myprint('yup')

prefix = 'foo'
mytable = {
  [prefix..'key'] = 111,
  barkey= 222;
  333
}

a=1; b=2; c=3

if ((x < 1) or (x > width) or (y < 1) or (y > height)) then
  return 0
end
'''.split(b'\n')]


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
        self.assertEqual(5, result.get_token_count())

    def testGetTokenCountCarriageReturns(self):
        result = lua.Lua.from_lines([
            b'function foo()\r\n',
            b'  return 999\r\n',
            b'end\r\n'
        ], 4)
        self.assertEqual(5, result.get_token_count())
        
    def testGetTitle(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        self.assertEqual(b'short test', result.get_title())

    def testGetByline(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        self.assertEqual(b'by dan', result.get_byline())

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
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES + [b'break'], 4)
        lines = list(result.to_lines())
        self.assertEqual(lines, VALID_LUA_SHORT_LINES + [b'break'])


class TestLuaASTEchoWriter(unittest.TestCase):
    def testToLinesASTEchoWriter(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaASTEchoWriter))
        self.assertEqual(lines, VALID_LUA_SHORT_LINES)

    def testToLinesASTEchoWriterEveryNode(self):
        result = lua.Lua.from_lines(VALID_LUA_EVERY_NODE, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaASTEchoWriter))
        self.assertEqual(lines, VALID_LUA_EVERY_NODE)


class TestLuaMinifyWriter(unittest.TestCase):
    def testMinifiesNames(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaMinifyWriter))
        txt = b''.join(lines)
        self.assertIn(b'function a()', txt)
        
    def testMinifiesNamesEveryNode(self):
        result = lua.Lua.from_lines(VALID_LUA_EVERY_NODE, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaMinifyWriter))
        txt = b''.join(lines)
        self.assertIn(b'function a(b,', txt)
        self.assertIn(b'local c', txt)
        self.assertIn(b'c[b]', txt)
        self.assertIn(b'return c', txt)
        self.assertIn(b'local function d(e)', txt)
        self.assertIn(b'print(e)', txt)

    def testMinifiesSpaces(self):
        result = lua.Lua.from_lines(VALID_LUA_SHORT_LINES, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaMinifyWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''function a()
return 999
end''', txt)
        
    def testMinifiesSpacesEveryNode(self):
        result = lua.Lua.from_lines(VALID_LUA_EVERY_NODE, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaMinifyWriter))
        txt = b''.join(lines)
        self.assertNotIn(b'-- the code with the nodes', txt)
        self.assertIn(b'''while f < 10 do
f += 1
if f % 2 == 0 then
a(f)
elseif f > 5 then
a(f, 5)
else
a(f, 1)
g *= 2
end
end
''', txt)
        self.assertIn(b'''for g in i() do
a(g)
end
''', txt)
        self.assertIn(b'f=1  n=2  o=3', txt)

    def testMinifyTokenWriterMinifiesSpacesEveryNode(self):
        result = lua.Lua.from_lines(VALID_LUA_EVERY_NODE, 4)
        lines = list(result.to_lines(writer_cls=lua.LuaMinifyTokenWriter))
        txt = b''.join(lines)
        self.assertNotIn(b'-- the code with the nodes', txt)
        self.assertIn(b'while f<10 do f+=1 if f%2==0 then\na(f)elseif f>5 then a(f,5)else a(f,1)g*=2 end end', txt)
        self.assertIn(b'for g in i()do a(g)end', txt)
        self.assertIn(b'f=1;n=2;o=3', txt)


class TestLuaFormatterWriter(unittest.TestCase):
    def testNormalizesSpaceCharacters(self):
        result = lua.Lua.from_lines([b'a\t=\tb\r\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b\n', txt)

    def testTrailingWhitespace(self):
        result = lua.Lua.from_lines([b'a = b   \nc = d   \n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b\nc = d\n', txt)

    def testCommentAtEndOfLine(self):
        result = lua.Lua.from_lines([b'a = b     -- comment\nc = d\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b  -- comment\nc = d\n', txt)

    def testCommentOnOwnLine(self):
        result = lua.Lua.from_lines([b'a = b\n    -- comment\nc = d\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b\n-- comment\nc = d\n', txt)

    def testIndentZero(self):
        result = lua.Lua.from_lines([b'\n  a = b\n        c = d\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'\na = b\nc = d\n', txt)

    def testIndentBlock(self):
        result = lua.Lua.from_lines([b'''
a = 1
do
b = 2
    c = 3
end
 d = 4

while foo do
 e = 5
  end
repeat
  f = 6
 g = 7
    h = 8
until foo

if foo then
 i = 9
  elseif bar then
   j = 10
    else
     k = 11
      end

for x=1,10,2 do
      l = 12
       m = 13
end
for x in foo do
        n = 14
         o = 15
end
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
a = 1
do
  b = 2
  c = 3
end
d = 4

while foo do
  e = 5
end
repeat
  f = 6
  g = 7
  h = 8
until foo

if foo then
  i = 9
elseif bar then
  j = 10
else
  k = 11
end

for x=1,10,2 do
  l = 12
  m = 13
end
for x in foo do
  n = 14
  o = 15
end
''', txt)

    def testIndentMulti(self):
        result = lua.Lua.from_lines([b'''
do
a = 1
while foo do
b = 2
if bar then
c = 3
elseif baz then
d = 4
repeat
e = 5
until bing
else
f = 6
end
end
g = 7
end
h = 8
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
do
  a = 1
  while foo do
    b = 2
    if bar then
      c = 3
    elseif baz then
      d = 4
      repeat
        e = 5
      until bing
    else
      f = 6
    end
  end
  g = 7
end
h = 8
''', txt)

    def testIndentCommentsAndStatements(self):
        result = lua.Lua.from_lines([b'''
 x += 1    -- increment x
do
-- do stuff in here
 print "stuff happens"
x -= 1      -- decrement x
end
 -- END
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
x += 1  -- increment x
do
  -- do stuff in here
  print "stuff happens"
  x -= 1  -- decrement x
end
-- END
''', txt)

    def testIndentTableConstructor(self):
        result = lua.Lua.from_lines([b'''
obj = {
foo=function(arg)
 a = 1
  b = 2
   c = 3
    end,
     bar=function(arg, arg, arg)
      d = 4
       e = 5
        end,
         baz=999
          }
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
obj = {
  foo=function(arg)
    a = 1
    b = 2
    c = 3
  end,
  bar=function(arg, arg, arg)
    d = 4
    e = 5
  end,
  baz=999
}
''', txt)

    def testTooManyNewlines(self):
        result = lua.Lua.from_lines([b'''


 a = 1




  b = 2


   c = 3
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''

a = 1

b = 2

c = 3
''', txt)

    def testAcceptsIndentWidthArg(self):
        result = lua.Lua.from_lines([b'''
do
a = 1
while foo do
b = 2
if bar then
c = 3
elseif baz then
d = 4
repeat
e = 5
until bing
else
f = 6
end
end
g = 7
end
h = 8
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterWriter,
                                     writer_args={'indentwidth':3}))
        txt = b''.join(lines)
        self.assertEqual(b'''
do
   a = 1
   while foo do
      b = 2
      if bar then
         c = 3
      elseif baz then
         d = 4
         repeat
            e = 5
         until bing
      else
         f = 6
      end
   end
   g = 7
end
h = 8
''', txt)


class TestLuaFormatterTokenWriter(unittest.TestCase):
    def testNormalizesSpaceCharacters(self):
        result = lua.Lua.from_lines([b'a\t=\tb\r\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b\n', txt)

    def testTrailingWhitespace(self):
        result = lua.Lua.from_lines([b'a = b   \nc = d   \n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b\nc = d\n', txt)

    def testCommentAtEndOfLine(self):
        result = lua.Lua.from_lines([b'a = b     -- comment\nc = d\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b  -- comment\nc = d\n', txt)

    def testCommentOnOwnLine(self):
        result = lua.Lua.from_lines([b'a = b\n    -- comment\nc = d\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = b\n-- comment\nc = d\n', txt)

    def testIndentZero(self):
        result = lua.Lua.from_lines([b'\n  a = b\n        c = d\n'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'\na = b\nc = d\n', txt)

    def testIndentBlock(self):
        result = lua.Lua.from_lines([b'''
a = 1
do
b = 2
    c = 3
end
 d = 4

while foo do
 e = 5
  end
repeat
  f = 6
 g = 7
    h = 8
until foo

if foo then
 i = 9
  elseif bar then
   j = 10
    else
     k = 11
      end

for x=1,10,2 do
      l = 12
       m = 13
end
for x in foo do
        n = 14
         o = 15
end
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
a = 1
do
  b = 2
  c = 3
end
d = 4

while foo do
  e = 5
end
repeat
  f = 6
  g = 7
  h = 8
until foo

if foo then
  i = 9
elseif bar then
  j = 10
else
  k = 11
end

for x = 1, 10, 2 do
  l = 12
  m = 13
end
for x in foo do
  n = 14
  o = 15
end
''', txt)

    def testIndentMulti(self):
        result = lua.Lua.from_lines([b'''
do
a = 1
while foo do
b = 2
if bar then
c = 3
elseif baz then
d = 4
repeat
e = 5
until bing
else
f = 6
end
end
g = 7
end
h = 8
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
do
  a = 1
  while foo do
    b = 2
    if bar then
      c = 3
    elseif baz then
      d = 4
      repeat
        e = 5
      until bing
    else
      f = 6
    end
  end
  g = 7
end
h = 8
''', txt)

    def testIndentCommentsAndStatements(self):
        result = lua.Lua.from_lines([b'''
 x += 1    -- increment x
do
-- do stuff in here
 print "stuff happens"
x -= 1      -- decrement x
end
 -- END
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
x += 1  -- increment x
do
  -- do stuff in here
  print "stuff happens"
  x -= 1  -- decrement x
end
-- END
''', txt)

    def testIndentTableConstructor(self):
        result = lua.Lua.from_lines([b'''
obj = {
foo=function(arg)
 a = 1
  b = 2
   c = 3
    end,
     bar=function(arg, arg, arg)
      d = 4
       e = 5
        end,
         baz=999
          }
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''
obj = {
  foo = function(arg)
    a = 1
    b = 2
    c = 3
  end,
  bar = function(arg, arg, arg)
    d = 4
    e = 5
  end,
  baz = 999
}
''', txt)

    def testTooManyNewlines(self):
        result = lua.Lua.from_lines([b'''


 a = 1




  b = 2


   c = 3
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'''

a = 1

b = 2

c = 3
''', txt)

    def testAcceptsIndentWidthArg(self):
        result = lua.Lua.from_lines([b'''
do
a = 1
while foo do
b = 2
if bar then
c = 3
elseif baz then
d = 4
repeat
e = 5
until bing
else
f = 6
end
end
g = 7
end
h = 8
'''], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter,
                                     writer_args={'indentwidth':3}))
        txt = b''.join(lines)
        self.assertEqual(b'''
do
   a = 1
   while foo do
      b = 2
      if bar then
         c = 3
      elseif baz then
         d = 4
         repeat
            e = 5
         until bing
      else
         f = 6
      end
   end
   g = 7
end
h = 8
''', txt)

    def testEliminateSpaceAroundSomePunctuation(self):
        result = lua.Lua.from_lines([b'a  =   {   "x" ,  y,  -3, 4+5*6}'], 4)
        lines = list(result.to_lines(writer_cls=lua.LuaFormatterTokenWriter))
        txt = b''.join(lines)
        self.assertEqual(b'a = {"x", y, - 3, 4 + 5 * 6}\n', txt)


if __name__ == '__main__':
    unittest.main()
