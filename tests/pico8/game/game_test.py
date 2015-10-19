#!/usr/bin/env python3

import io
import os
import textwrap
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.game import game
from pico8.lua import lexer
from pico8.lua import parser


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


class TestP8Game(unittest.TestCase):
    def setUp(self):
        self.testdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'testdata')
        
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

    def testFromP8FileGoL(self):
        p8path = os.path.join(self.testdata_path, 'test_gol.p8')
        with open(p8path, 'r') as fh:
            p8game = game.Game.from_p8_file(fh)
        # TODO: validate game
        
        
class TestP8PNGGame(unittest.TestCase):
    def setUp(self):
        self.testdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'testdata')

    def testFromP8PNGFileV0(self):
        pngpath = os.path.join(self.testdata_path, 'helloworld.p8.png')
        with open(pngpath, 'rb') as fh:
            pnggame = game.Game.from_p8png_file(fh)
        first_stat = pnggame.lua.root.stats[0]
        self.assertTrue(isinstance(first_stat, parser.StatAssignment))
        tokens = pnggame.lua.tokens
        self.assertEqual(lexer.TokComment('-- hello world'), tokens[0])
        self.assertEqual(lexer.TokNewline('\n'), tokens[1])
        self.assertEqual(lexer.TokComment('-- by zep'), tokens[2])
        self.assertEqual(lexer.TokNewline('\n'), tokens[3])
        
    def testFromP8PNGFile(self):
        pngpath = os.path.join(self.testdata_path, 'test_gol.p8.png')
        with open(pngpath, 'rb') as fh:
            pnggame = game.Game.from_p8png_file(fh)
        # TODO: validate game

    
if __name__ == '__main__':
    unittest.main()
