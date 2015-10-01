#!/usr/bin/env python3

import io
import textwrap
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.game import game


VALID_P8_HEADER = '''pico-8 cartridge // http://www.pico-8.com
version 4
'''

INVALID_P8_HEADER_ONE = '''INVALID HEADER
version 4
'''

INVALID_P8_HEADER_TWO = '''pico-8 cartridge // http://www.pico-8.com
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


class TestGame(unittest.TestCase):
    def testFromP8File(self):
        g = game.Game.from_p8_file(io.StringIO(
            VALID_P8_HEADER +
            VALID_P8_LUA_SECTION_HEADER +
            VALID_P8_FOOTER))
        self.assertEqual(4, g.lua._version)
        self.assertEqual(4, g.gfx._version)
        self.assertEqual(4, g.gff._version)
        self.assertEqual(4, g.map._version)
        self.assertEqual(4, g.sfx._version)
        self.assertEqual(4, g.music._version)

    def testInvalidP8HeaderErrorMsg(self):
        # coverage
        txt = str(game.InvalidP8HeaderError())

    def testInvalidP8SectionErrorMsg(self):
        # coverage
        txt = str(game.InvalidP8SectionError('bad'))
        
    def testInvalidP8HeaderLineOne(self):
        self.assertRaises(
            game.InvalidP8HeaderError,
            game.Game.from_p8_file,
            io.StringIO(
            INVALID_P8_HEADER_ONE +
            VALID_P8_LUA_SECTION_HEADER +
            VALID_P8_FOOTER))

    def testInvalidP8HeaderLineTwo(self):
        self.assertRaises(
            game.InvalidP8HeaderError,
            game.Game.from_p8_file,
            io.StringIO(
            INVALID_P8_HEADER_TWO +
            VALID_P8_LUA_SECTION_HEADER +
            VALID_P8_FOOTER))

    def testInvalidP8Section(self):
        self.assertRaises(
            game.InvalidP8SectionError,
            game.Game.from_p8_file,
            io.StringIO(
            VALID_P8_HEADER +
            VALID_P8_LUA_SECTION_HEADER +
            '\n__bad__\n\n' +
            VALID_P8_FOOTER))


if __name__ == '__main__':
    unittest.main()
