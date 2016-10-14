#!/usr/bin/env python3

import png
import io
import os
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8 import util
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

CODE_UNCOMPRESSED_BYTES = bytearray([
    102, 111, 114, 32, 105, 61, 49, 44, 49, 48, 32, 100, 111, 10, 32, 32, 112,
    114, 105, 110, 116, 40, 34, 104, 105, 32, 34, 46, 46, 105, 41, 10, 101, 110,
    100, 10])

CODE_COMPRESSED_BYTES = bytearray([
    58, 99, 58, 0, 0, 142, 0, 0, 0, 45, 0, 45, 2, 31, 27, 25, 17, 2, 32, 21, 32,
    24, 17, 1, 60, 110, 13, 33, 32, 20, 27, 30, 1, 1, 18, 27, 30, 2, 21, 51, 4,
    57, 4, 3, 2, 16, 27, 1, 2, 2, 28, 30, 21, 26, 32, 42, 0, 34, 20, 21, 2, 0,
    34, 56, 56, 21, 43, 1, 0, 9, 2, 21, 18, 2, 21, 2, 41, 2, 6, 2, 32, 20, 17,
    26, 61, 16, 62, 116, 14, 33, 38, 38, 0, 34, 62, 34, 61, 242, 62, 244, 0, 9,
    2, 17, 26, 16, 1, 60, 36])

CODE_COMPRESSED_AS_STRING = '''-- some title
-- some author

for i=1,10 do
  print("hi "..i)
	 if i % 3 then
	   print("buzz")
	   print("buzz")
	   print("buzz")
	 end
end

'''

FILE_TEST_GOL_CODE_COMPRESSED_HEAD = [
    58, 99, 58, 0, 4, 194, 0, 0, 0, 45, 0, 45, 2, 19, 13, 25, 17, 2, 27, 18,
    2, 24, 21, 18]

TEST_PNG = {
    'width': 3,
    'height': 3,
    'data': [[0xec, 0xdc, 0xcc, 0xfc,    # 0
              0xac, 0x9c, 0x8d, 0xbc,    # 1
              0x6c, 0x5c, 0x4e, 0x7c],   # 2
             [0xec, 0xdc, 0xcf, 0xfc,    # 3
              0xac, 0x9d, 0x8c, 0xbc,    # 4
              0x6c, 0x5d, 0x4d, 0x7c],   # 5
             [0xec, 0xdd, 0xce, 0xfc,    # 6
              0xac, 0x9d, 0x8f, 0xbc,    # 7
              0x6f, 0x5f, 0x4f, 0x7f]],  # 255
    'attrs': {'planes': 4}
}

TEST_PNG_PICODATA = [0, 1, 2, 3, 4, 5, 6, 7, 255]

TEST_PNG_BLANK_DATA = [
             [0xef, 0xdf, 0xcf, 0xff,
              0xaf, 0x9f, 0x8f, 0xbf,
              0x6f, 0x5f, 0x4f, 0x7f],
             [0xef, 0xdf, 0xcf, 0xff,
              0xaf, 0x9f, 0x8f, 0xbf,
              0x6f, 0x5f, 0x4f, 0x7f],
             [0xef, 0xdf, 0xcf, 0xff,
              0xaf, 0x9f, 0x8f, 0xbf,
              0x6f, 0x5f, 0x4f, 0x7f]]


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
        pngpath = os.path.join(self.testdata_path, 'test_cart.p8.png')
        with open(pngpath, 'rb') as fh:
            pnggame = game.Game.from_p8png_file(fh)
        first_stat = pnggame.lua.root.stats[0]
        self.assertTrue(isinstance(first_stat, parser.StatFunctionCall))
        tokens = pnggame.lua.tokens
        self.assertEqual(lexer.TokComment('-- memory dump'), tokens[0])
        self.assertEqual(lexer.TokNewline('\n'), tokens[1])
        self.assertEqual(lexer.TokComment('-- by dddaaannn'), tokens[2])
        self.assertEqual(lexer.TokNewline('\n'), tokens[3])

    def testFromP8PNGFile(self):
        pngpath = os.path.join(self.testdata_path, 'test_gol.p8.png')
        with open(pngpath, 'rb') as fh:
            pnggame = game.Game.from_p8png_file(fh)
            # TODO: validate game

    def testGetCodeFromBytesUncompressed(self):
        codedata = [0] * (0x8000 - 0x4300)
        codedata[:len(CODE_UNCOMPRESSED_BYTES)] = CODE_UNCOMPRESSED_BYTES
        code_length, code, compressed_size = \
            game.Game.get_code_from_bytes(codedata, 1)
        self.assertEqual(len(CODE_UNCOMPRESSED_BYTES), code_length)
        # (added trailing newline)
        self.assertEqual(CODE_UNCOMPRESSED_BYTES.decode('utf-8') + '\n', code)
        self.assertIsNone(compressed_size)

    def testGetCodeFromBytesCompressed(self):
        codedata = [0] * (0x8000 - 0x4300)
        codedata[:len(CODE_COMPRESSED_BYTES)] = CODE_COMPRESSED_BYTES
        code_length, code, compressed_size = \
            game.Game.get_code_from_bytes(codedata, 1)
        # (len - 1 because of added trailing newline)
        self.assertEqual(len(CODE_COMPRESSED_AS_STRING) - 1, code_length)
        self.assertEqual(CODE_COMPRESSED_AS_STRING, code)
        self.assertEqual(len(CODE_COMPRESSED_BYTES), compressed_size)

    def testPngToPicodataSimple(self):
        picodata = game.Game.get_picodata_from_pngdata(
            TEST_PNG['width'], TEST_PNG['height'],
            TEST_PNG['data'], TEST_PNG['attrs'])
        self.assertEqual(TEST_PNG_PICODATA, picodata)

    def testPngToPicodataFromFile(self):
        pngpath = os.path.join(self.testdata_path, 'test_gol.p8.png')
        with open(pngpath, 'rb') as fh:
            width, height, data, attrs = png.Reader(file=fh).read()
            data = list(data)
        picodata = game.Game.get_picodata_from_pngdata(
            width, height, data, attrs)
        self.assertEqual(len(picodata), 32800)
        self.assertEqual(FILE_TEST_GOL_CODE_COMPRESSED_HEAD,
                         picodata[0x4300:
                         0x4300 + len(FILE_TEST_GOL_CODE_COMPRESSED_HEAD)])

    def testPicodataToPngSimple(self):
        pngdata = game.Game.get_pngdata_from_picodata(TEST_PNG_PICODATA,
                                                      TEST_PNG_BLANK_DATA,
                                                      TEST_PNG['attrs'])
        for row_i in range(len(pngdata)):
            self.assertEqual(bytearray(TEST_PNG['data'][row_i]), pngdata[row_i])

    def testCompressCodeHelloExample(self):
        test_str = ('a="hello"\nb="hello also"\nb="hello also"\n'
                    'b="hello also"\nb="hello also"\nb="hello also"\n'
                    'b="hello also"\n\n')
        comp_result = game.Game.compress_code(test_str)
        code_length_bytes = bytes([len(test_str) >> 8, len(test_str) & 255])
        code_bytes = b''.join([b':c:\0', code_length_bytes, b'\0\0',
                               comp_result])
        decomp_result = game.Game.decompress_code(code_bytes)
        self.assertEqual(decomp_result[1], test_str + '\n')
        # TODO: actual Pico-8 result:
        #self.assertEqual(bytearray([13, 51, 0, 34, 20, 17, 24, 24, 27, 0, 34, 1, 14, 60, 90, 2, 13, 24, 31, 60, 223, 61, 254, 62, 253, 63, 252, 64, 171]),
        #    result)

class TestGameToP8(unittest.TestCase):
    def setUp(self):
        self.testdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'testdata')
        self.orig_error_stream = util._error_stream
        util._error_stream = io.StringIO()

    def tearDown(self):
        util._error_stream = self.orig_error_stream

    def testToP8FileFromP8(self):
        with open(os.path.join(self.testdata_path, 'test_cart.p8')) as fh:
            orig_game = game.Game.from_p8_file(fh)
        with open(os.path.join(self.testdata_path, 'test_cart.p8')) as fh:
            expected_game_p8 = fh.read()
        outstr = io.StringIO()
        orig_game.to_p8_file(outstr)
        self.assertEqual(expected_game_p8, outstr.getvalue())

    def testToP8FileFromPng(self):
        with open(os.path.join(self.testdata_path, 'test_cart.p8.png'),
                  'rb') as fh:
            orig_game = game.Game.from_p8png_file(fh)
        with open(os.path.join(self.testdata_path, 'test_cart.p8')) as fh:
            expected_game_p8 = fh.read()
        outstr = io.StringIO()
        orig_game.to_p8_file(outstr)
        self.assertEqual(expected_game_p8, outstr.getvalue())

    def testCharCountWarning(self):
        g = game.Game.make_empty_game(filename='test')
        g.lua.update_from_lines(
            ['-- 345678901234567890123456789012345678\n'] * 820)
        outstr = io.StringIO()
        g.to_p8_file(outstr, filename='test')
        self.assertTrue(util._error_stream.getvalue().startswith(
            'test: warning: character count'))

    def testTokenCountWarning(self):
        g = game.Game.make_empty_game()
        g.lua.update_from_lines(
            ['a=b=c=d=e=f=g=h=i=j=k=l=m=n=o=p=q=r=s=t=u\n'] * 199 +
            ['a=b=c=d=e=f=g=h=i=j=k=l=m=n=o=p=q=r=s=t=u'])
        outstr = io.StringIO()
        g.to_p8_file(outstr)
        self.assertTrue(util._error_stream.getvalue().startswith(
            'warning: token count'))


class TestGameToP8PNG(unittest.TestCase):
    def setUp(self):
        self.testdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'testdata')
        self.orig_error_stream = util._error_stream
        util._error_stream = io.StringIO()

    def tearDown(self):
        util._error_stream = self.orig_error_stream

        # TODO:
        # def testToPngFromPng(self):
        #     with open(os.path.join(self.testdata_path, 'test_cart.p8.png'),
        #  'rb') as fh:
        #         orig_game = game.Game.from_p8png_file(fh)
        #     with open(os.path.join(self.testdata_path, 'test_cart.p8.png'),
        #  'rb') as fh:
        #         expected_game_p8 = fh.read()
        #     outstr = io.BytesIO()
        #     orig_game.to_p8png_file(
        #         outstr,
        #         label_fname=os.path.join(self.testdata_path,
        # 'test_cart.p8.png'))
        #     self.assertEqual(expected_game_p8, outstr.getvalue())


if __name__ == '__main__':
    unittest.main()
