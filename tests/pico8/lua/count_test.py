#!/usr/bin/env python3

"""Tests specifically about refining character and token counts to match PICO-8.

So far this represents experiments from PICO-8 1.3.0.
"""

import io
import unittest

from pico8.game.formatter.p8 import P8Formatter


TESTS = (
    {'code':'''function t()
  print('hi')
end

t()
''', 'tokens': 8, 'chars': 36},

    {'code':'', 'tokens': 0, 'chars': 0},
    {'code':'-- comment\n', 'tokens': 0, 'chars': 11},
    {'code':'a=1\n', 'tokens': 3, 'chars': 4},
    {'code':'a = 1\n', 'tokens': 3, 'chars': 6},
    {'code':'abc = 123\n', 'tokens': 3, 'chars': 10},
    {'code':'abc = 123\ndef = 456\n', 'tokens': 6, 'chars': 20},
    {'code':'break\n', 'tokens': 1, 'chars': 6},
    {'code':'return\n', 'tokens': 1, 'chars': 7},
    {'code':'return 999\n', 'tokens': 2, 'chars': 11},
    {'code':'''abc = 123
def = 456
return 999
''', 'tokens': 8, 'chars': 31},
    {'code':'''do
  abc = 123
  def = 456
  return 999
end
''', 'tokens': 9, 'chars': 44},
    {'code':'''while true do
  abc = 123
  def = 456
  return 999
end
''', 'tokens': 11, 'chars': 55},
    {'code':'''repeat
  abc = 123
  def = 456
  return 999
until true
''', 'tokens': 11, 'chars': 55},
    {'code':'''if true then
  abc = 123
end
''', 'tokens': 6, 'chars': 29},
    {'code':'''if true then
  abc = 123
elseif false then
  def = 456
else
  ghi = 789
end
''', 'tokens': 16, 'chars': 76},
    {'code':'''for x=1,10,2 do
  abc = 123
end
''', 'tokens': 10, 'chars': 32},
    {'code':'''for a,b,c in 1,2,3 do
  abc = 123
end
''', 'tokens': 12, 'chars': 38},
    {'code':'''function f()
  return 999
end
''', 'tokens': 5, 'chars': 30},
    {'code':'''local function f()
  return 999
end
''', 'tokens': 5, 'chars': 36},
    {'code':'local a,b,c\n', 'tokens': 3, 'chars': 12},
    {'code':'local a,b,c = 1,2,3\n', 'tokens': 7, 'chars': 20},
    {'code':'''function f.a.b()
  return 999
end
''', 'tokens': 7, 'chars': 34},
    {'code':'''function f.a.b:c()
  return 999
end
''', 'tokens': 8, 'chars': 36},
    {'code':'a[1] = 2\n', 'tokens': 5, 'chars': 9},
    {'code':'a.b = 2\n', 'tokens': 4, 'chars': 8},
    {'code':'''a=nil
b=false
c=true
''', 'tokens': 9, 'chars': 21},
    {'code':'a = 123\n', 'tokens': 3, 'chars': 8},
    {'code':'a = -123\n', 'tokens': 3, 'chars': 9},
    {'code':'a = 123.45\n', 'tokens': 3, 'chars': 11},
    {'code':'a = 123.45e2\n', 'tokens': 4, 'chars': 13},
    {'code':'a = -123.45e2\n', 'tokens': 4, 'chars': 14},
    {'code':'a = \'string\'\n', 'tokens': 3, 'chars': 13},
    {'code':'a = "string"\n', 'tokens': 3, 'chars': 13},
    {'code':'function f(...)\nend\n', 'tokens': 4, 'chars': 20},
    {'code':'a += 3\n', 'tokens': 3, 'chars': 7},
    {'code':'c = a != 3\n', 'tokens': 5, 'chars': 11},
    {'code':'c = #a\n', 'tokens': 4, 'chars': 7},
    {'code':'c:m()\n', 'tokens': 3, 'chars': 6},
    {'code':'a = {}\n', 'tokens': 3, 'chars': 7},
    {'code':'a = {[a]=3;b=4,999}\n', 'tokens': 11, 'chars': 20},
    {'code':'print(a..b)\n', 'tokens': 5, 'chars': 12},
    {'code':'''goto label
print('one')
::label::
print('two')
''', 'tokens': 9, 'chars': 47},
    {'code':'function t()\n\treturn\nend\n', 'tokens': 4, 'chars': 25},

#     # Cart 12373
#     {'code':'''function _init()
# 	load("main.p8")
# end
# ''', 'tokens': 10, 'chars': 37},

#     # Cart 10516
#     {'code':'''-- bigimg by ccatgames
# -- twitter: (at)viza
# cls()
# sspr(0,0,127,127,0,0)

# function _update()
# end

# function _draw()
# end

# ''', 'tokens': 30, 'chars': 119},

#     # Cart 11109
#     {'code':'''function _update()
# end

# function _draw()
#   cls()
#   mapdraw(0, 0, 41, 37, 3, 5)
# end
# ''', 'tokens': 29, 'chars': 82},

#     # Cart 12382
#     {'code':'''function _init()
# 	pset(30,30,10)
# 	pset(30,31,11)
# 	load("cart2.p8")
# 	run()
# end
# ''', 'tokens': 29, 'chars': 77},

#     # Cart 12148
#     {'code':'''::loop::
# map(0,0,0,0,16,16)
# memcpy(0x2000,0x6002,0x1000)
# flip()
# goto loop
# ''', 'tokens': 30, 'chars': 75},

)


VALID_P8_HEADER = b'''pico-8 cartridge // http://www.pico-8.com
version 4
'''

VALID_P8_LUA_SECTION_HEADER = b'__lua__\n'

VALID_P8_FOOTER = (
    b'__gfx__\n' + ((b'0' * 128) + b'\n') * 128 +
    b'__gff__\n' + ((b'0' * 256) + b'\n') * 2 +
    b'__map__\n' + ((b'0' * 256) + b'\n') * 32 +
    b'__sfx__\n' + b'0001' + (b'0' * 164) + b'\n' +
    (b'001' + (b'0' * 165) + b'\n') * 63 +
    b'__music__\n' + b'00 41424344\n' * 64 + b'\n\n')


class TestCounts(unittest.TestCase):
    def testCharCounts(self):
        for t in TESTS:
            g = P8Formatter.from_file(io.BytesIO(
                VALID_P8_HEADER +
                VALID_P8_LUA_SECTION_HEADER +
                bytes(t['code'], encoding='ascii') +
                VALID_P8_FOOTER))
            self.assertEqual(t['chars'], g.lua.get_char_count(),
                             'Mismatched char count: ' + repr(t['code']))

    def testTokenCounts(self):
        for t in TESTS:
            g = P8Formatter.from_file(io.BytesIO(
                VALID_P8_HEADER +
                VALID_P8_LUA_SECTION_HEADER +
                bytes(t['code'], encoding='ascii') +
                VALID_P8_FOOTER))
            self.assertEqual(t['tokens'], g.lua.get_token_count(),
                             'Mismatched token count: ' + repr(t['code']))


if __name__ == '__main__':
    unittest.main()
