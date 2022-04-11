#!/usr/bin/env python3

import io
import os
import png
import shutil
import tempfile
import unittest

from pico8 import util
from pico8.game import compress
from pico8.game import file
from pico8.game import game
from pico8.game.formatter import p8
from pico8.game.formatter import p8png
from pico8.game.formatter import rom
from pico8.lua import lexer
from pico8.lua import parser

VALID_P8_HEADER = b'''pico-8 cartridge // http://www.pico-8.com
version 4
'''

INVALID_P8_HEADER_ONE = b'''INVALID HEADER
version 4
'''

INVALID_P8_HEADER_TWO = b'''pico-8 cartridge // http://www.pico-8.com
INVALID HEADER
'''

VALID_P8_LUA_SECTION_HEADER = b'__lua__\n'

VALID_P8_FOOTER = (
    b'\n__gfx__\n' + ((b'0' * 128) + b'\n') * 128 +
    b'__gff__\n' + ((b'0' * 256) + b'\n') * 2 +
    b'__map__\n' + ((b'0' * 256) + b'\n') * 32 +
    b'__sfx__\n' + b'0001' + (b'0' * 164) + b'\n' +
    (b'001' + (b'0' * 165) + b'\n') * 63 +
    b'__music__\n' + b'00 41424344\n' * 64 + b'\n\n')

CODE_UNCOMPRESSED_BYTES = bytearray([
    102, 111, 114, 32, 105, 61, 49, 44, 49, 48, 32, 100, 111, 10, 32, 32, 112,
    114, 105, 110, 116, 40, 34, 104, 105, 32, 34, 46, 46, 105, 41, 10, 101,
    110, 100, 10])

CODE_COMPRESSED_BYTES = bytearray([
    58, 99, 58, 0, 0, 142, 0, 0, 0, 45, 0, 45, 2, 31, 27, 25, 17, 2, 32, 21,
    32, 24, 17, 1, 60, 110, 13, 33, 32, 20, 27, 30, 1, 1, 18, 27, 30, 2, 21,
    51, 4, 57, 4, 3, 2, 16, 27, 1, 2, 2, 28, 30, 21, 26, 32, 42, 0, 34, 20,
    21, 2, 0, 34, 56, 56, 21, 43, 1, 0, 9, 2, 21, 18, 2, 21, 2, 41, 2, 6, 2,
    32, 20, 17, 26, 61, 16, 62, 116, 14, 33, 38, 38, 0, 34, 62, 34, 61, 242,
    62, 244, 0, 9, 2, 17, 26, 16, 1, 60, 36])

# Intentional mix of tabs and spaces, don't change!
CODE_COMPRESSED_AS_STRING = b'''-- some title
-- some author

for i=1,10 do
  print("hi "..i)
	 if i % 3 then
	   print("buzz")
	   print("buzz")
	   print("buzz")
	 end
end
'''  # noqa: E101, W191

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

CODE_WITH_TABS = b'''
print('zero')
-->8
print('one')
-- some other comment
-->8
print('two')

if (btnp(8)) mode=2
-->8
print('three')
'''

CODE_WITH_TABS_TAB_TWO = b'''
print('two')

if (btnp(8)) mode=2
'''

CODE_WITH_INCLUDE_LUA = b'''
print('before include')
#include inc.lua
print('after include')
'''

CODE_WITH_INCLUDE_P8 = b'''
print('before include')
#include inc.p8
print('after include')
'''

CODE_WITH_INCLUDE_P8_TAB = b'''
print('before include')
#include inc.p8:2
print('after include')
'''

CODE_WITH_INCLUDE_P8PNG = b'''
print('before include')
#include inc.p8.png
print('after include')
'''

CODE_WITH_INCLUDE_P8PNG_TAB = b'''
print('before include')
#include inc.p8.png:2
print('after include')
'''

CODE_WITH_INCLUDE_LUA_SUBDIR = b'''
print('before include')
#include subdir/inc.lua
print('after include')
'''

CODE_WITH_INCLUDE_LUA_PARENT_DIR = b'''
print('before include')
#include ../inc.lua
print('after include')
'''


def make_test_cart_from_code(dirname, fname, luabytes, is_p8png=False):
    fmtcls = p8png.P8PNGFormatter if is_p8png else p8.P8Formatter
    g = game.Game.make_empty_game(fname)
    g.lua.update_from_lines([
        line + b'\n' for line in luabytes.strip().split(b'\n')])
    cart_path = os.path.join(dirname, fname)
    with open(cart_path, 'wb') as fh:
        fmtcls.to_file(g, fh, filename=os.path.join(dirname, fname))


def make_expected_with_include(inner):
    return (
        b'print(\'before include\')\n' +
        inner.strip() +
        b'\nprint(\'after include\')\n')


class TestP8Game(unittest.TestCase):
    def setUp(self):
        self.testdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'testdata')

    def testFromP8File(self):
        g = p8.P8Formatter.from_file(io.BytesIO(
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
        str(p8.InvalidP8HeaderError('bad', 'expected'))

    def testInvalidP8VersionErrorMsg(self):
        # coverage
        str(p8.InvalidP8VersionError('bad version'))

    def testInvalidP8SectionErrorMsg(self):
        # coverage
        str(p8.InvalidP8SectionError('bad'))

    def testInvalidP8HeaderLineOne(self):
        self.assertRaises(
            p8.InvalidP8HeaderError,
            p8.P8Formatter.from_file,
            io.BytesIO(
                INVALID_P8_HEADER_ONE +
                VALID_P8_LUA_SECTION_HEADER +
                VALID_P8_FOOTER))

    def testInvalidP8HeaderLineTwo(self):
        self.assertRaises(
            p8.InvalidP8VersionError,
            p8.P8Formatter.from_file,
            io.BytesIO(
                INVALID_P8_HEADER_TWO +
                VALID_P8_LUA_SECTION_HEADER +
                VALID_P8_FOOTER))

    def testInvalidP8Section(self):
        self.assertRaises(
            p8.InvalidP8SectionError,
            p8.P8Formatter.from_file,
            io.BytesIO(
                VALID_P8_HEADER +
                VALID_P8_LUA_SECTION_HEADER +
                b'\n__bad__\n\n' +
                VALID_P8_FOOTER))

    def testFromP8FileGoL(self):
        p8path = os.path.join(self.testdata_path, 'test_gol.p8')
        with open(p8path, 'rb') as fh:
            p8.P8Formatter.from_file(fh)
            # TODO: validate game


class TestP8PNGGame(unittest.TestCase):
    def setUp(self):
        self.testdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'testdata')

    def testFromP8PNGFileV0(self):
        pngpath = os.path.join(self.testdata_path, 'test_cart_memdump.p8.png')
        with open(pngpath, 'rb') as fh:
            pnggame = p8png.P8PNGFormatter.from_file(fh)
        first_stat = pnggame.lua.root.stats[0]
        self.assertTrue(isinstance(first_stat, parser.StatFunctionCall))
        tokens = pnggame.lua.tokens
        self.assertEqual(lexer.TokComment(b'-- memory dump'), tokens[0])
        self.assertEqual(lexer.TokNewline(b'\n'), tokens[1])
        self.assertEqual(lexer.TokComment(b'-- by dddaaannn'), tokens[2])
        self.assertEqual(lexer.TokNewline(b'\n'), tokens[3])

    def testFromP8PNGFile(self):
        pngpath = os.path.join(self.testdata_path, 'test_gol.p8.png')
        with open(pngpath, 'rb') as fh:
            p8png.P8PNGFormatter.from_file(fh)
            # TODO: validate game

    def testGetCodeFromBytesUncompressed(self):
        codedata = [0] * (0x8000 - 0x4300)
        codedata[:len(CODE_UNCOMPRESSED_BYTES)] = CODE_UNCOMPRESSED_BYTES
        code_length, code, compressed_size = \
            p8png.get_code_from_bytes(codedata, 1)
        self.assertEqual(len(CODE_UNCOMPRESSED_BYTES), code_length)
        # (added trailing newline)
        self.assertEqual(CODE_UNCOMPRESSED_BYTES + b'\n', code)
        self.assertIsNone(compressed_size)

    def testGetCodeFromBytesCompressed(self):
        codedata = [0] * (0x8000 - 0x4300)
        codedata[:len(CODE_COMPRESSED_BYTES)] = CODE_COMPRESSED_BYTES
        code_length, code, compressed_size = \
            p8png.get_code_from_bytes(codedata, 1)
        self.assertEqual(len(CODE_COMPRESSED_AS_STRING), code_length)
        self.assertEqual(CODE_COMPRESSED_AS_STRING, code)
        self.assertEqual(len(CODE_COMPRESSED_BYTES), compressed_size)

    def testPngToPicodataSimple(self):
        picodata = p8png.get_picodata_from_pngdata(
            TEST_PNG['width'], TEST_PNG['height'],
            TEST_PNG['data'], TEST_PNG['attrs'])
        self.assertEqual(TEST_PNG_PICODATA, picodata)

    def testPngToPicodataFromFile(self):
        pngpath = os.path.join(self.testdata_path, 'test_gol.p8.png')
        with open(pngpath, 'rb') as fh:
            width, height, data, attrs = png.Reader(file=fh).read()
            data = list(data)
        picodata = p8png.get_picodata_from_pngdata(
            width, height, data, attrs)
        self.assertEqual(len(picodata), 32800)
        self.assertEqual(FILE_TEST_GOL_CODE_COMPRESSED_HEAD,
                         picodata[
                            0x4300:
                            0x4300 + len(FILE_TEST_GOL_CODE_COMPRESSED_HEAD)])

    def testPicodataToPngSimple(self):
        pngdata = p8png.get_pngdata_from_picodata(
            TEST_PNG_PICODATA,
            TEST_PNG_BLANK_DATA,
            TEST_PNG['attrs'])
        for row_i in range(len(pngdata)):
            self.assertEqual(
                bytearray(TEST_PNG['data'][row_i]),
                pngdata[row_i])

    def testCompressCodeHelloExample(self):
        test_str = (b'a="hello"\nb="hello also"\nb="hello also"\n'
                    b'b="hello also"\nb="hello also"\nb="hello also"\n'
                    b'b="hello also"\n\n')
        comp_result = compress.compress_code(test_str)
        code_length_bytes = bytes([len(test_str) >> 8, len(test_str) & 255])
        code_bytes = b''.join([b':c:\0', code_length_bytes, b'\0\0',
                               comp_result])
        decomp_result = compress.decompress_code(code_bytes)
        self.assertEqual(decomp_result[1], test_str)

        p8_comp_result = bytearray([
            13, 51, 0, 34, 20, 17, 24, 24, 27, 0, 34, 1, 14, 60, 90, 2, 13, 24,
            31, 60, 223, 61, 254, 62, 253, 63, 252, 64, 171, 1])
        self.assertEqual(len(comp_result), len(p8_comp_result))
        self.assertEqual(comp_result, p8_comp_result)


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
        test_cart_path = os.path.join(self.testdata_path, 'test_cart.p8')
        with open(test_cart_path, 'rb') as fh:
            orig_game = p8.P8Formatter.from_file(fh)
        with open(test_cart_path, 'rb') as fh:
            expected_game_p8 = fh.read()
        outstr = io.BytesIO()
        p8.P8Formatter.to_file(orig_game, outstr)
        self.assertEqual(expected_game_p8, outstr.getvalue())

    def testToP8FileFromP8WithCrlf(self):
        test_cart_path = os.path.join(self.testdata_path, 'test_cart_crlf.p8')
        with open(test_cart_path, 'rb') as fh:
            orig_game = p8.P8Formatter.from_file(fh)
        with open(test_cart_path, 'rb') as fh:
            expected_game_p8 = fh.read()
        outstr = io.BytesIO()
        p8.P8Formatter.to_file(orig_game, outstr)

        # It's not (yet) important for this tool to retain CRLF endings when building from a source p8 cart
        # which uses CRLF endings. It's ok for the resulting generated cart to use LF endings.
        expected_game_p8 = expected_game_p8.replace(b"\r", b"")
        outstr = outstr.getvalue().replace(b"\r", b"")

        self.assertEqual(expected_game_p8, outstr)

    def testToP8FileFromP8PreservesLabel(self):
        test_cart_path = os.path.join(
            self.testdata_path, 'test_cart_with_label.p8')
        with open(test_cart_path, 'rb') as fh:
            orig_game = p8.P8Formatter.from_file(fh)
        with open(test_cart_path, 'rb') as fh:
            expected_game_p8 = fh.read()
        outstr = io.BytesIO()
        p8.P8Formatter.to_file(orig_game, outstr)
        self.assertEqual(expected_game_p8, outstr.getvalue())

    def testToP8FileFromPng(self):
        test_cart_path_p8png = os.path.join(
            self.testdata_path, 'test_cart.p8.png')
        with open(test_cart_path_p8png, 'rb') as fh:
            orig_game = p8png.P8PNGFormatter.from_file(fh)
        test_cart_path_p8 = os.path.join(
            self.testdata_path, 'test_cart.p8')
        with open(test_cart_path_p8, 'rb') as fh:
            expected_game_p8 = fh.read()
        outstr = io.BytesIO()
        p8.P8Formatter.to_file(orig_game, outstr)
        self.assertEqual(expected_game_p8, outstr.getvalue())

    def testCharCountWarning(self):
        g = game.Game.make_empty_game(filename='test')
        g.lua.update_from_lines(
            [b'-- 345678901234567890123456789012345678\n'] * 1640)
        outstr = io.BytesIO()
        p8.P8Formatter.to_file(g, outstr, filename='test')
        self.assertTrue(util._error_stream.getvalue().startswith(
            'test: warning: character count'))

    def testTokenCountWarning(self):
        g = game.Game.make_empty_game()
        g.lua.update_from_lines(
            [b'a=b=c=d=e=f=g=h=i=j=k=l=m=n=o=p=q=r=s=t=u\n'] * 199 +
            [b'a=b=c=d=e=f=g=h=i=j=k=l=m=n=o=p=q=r=s=t=u'])
        outstr = io.BytesIO()
        p8.P8Formatter.to_file(g, outstr)
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
        #         orig_game = p8png.P8PNGFormatter.from_file(fh)
        #     with open(os.path.join(self.testdata_path, 'test_cart.p8.png'),
        #  'rb') as fh:
        #         expected_game_p8 = fh.read()
        #     outstr = io.BytesIO()
        #     orig_game.to_p8png_file(
        #         outstr,
        #         label_fname=os.path.join(self.testdata_path,
        # 'test_cart.p8.png'))
        #     self.assertEqual(expected_game_p8, outstr.getvalue())


class TestFile(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def testSelectsP8Formatter(self):
        assert file.formatter_for_filename('foo.p8') == p8.P8Formatter

    def testSelectsP8PNGFormatter(self):
        assert (
            file.formatter_for_filename('foo.p8.png') ==
            p8png.P8PNGFormatter)

    def testSelectsROMFormatter(self):
        assert file.formatter_for_filename('foo.rom') == rom.ROMFormatter

    def testUnrecognizedFileType(self):
        self.assertRaises(
            file.UnrecognizedFileType,
            file.formatter_for_filename,
            'foo.UNRECOGNIZED_FILE_TYPE')

    def testFromP8File(self):
        test_p8_path = os.path.join(self.tempdir, 'test.p8')
        with open(test_p8_path, 'wb') as fh:
            fh.write(
                VALID_P8_HEADER +
                VALID_P8_LUA_SECTION_HEADER +
                VALID_P8_FOOTER)
        g = file.from_file(test_p8_path)
        self.assertEqual(4, g.lua._version)
        self.assertEqual(4, g.gfx._version)
        self.assertEqual(4, g.gff._version)
        self.assertEqual(4, g.map._version)
        self.assertEqual(4, g.sfx._version)
        self.assertEqual(4, g.music._version)

    def testToFile(self):
        g = p8.P8Formatter.from_file(io.BytesIO(
            VALID_P8_HEADER +
            VALID_P8_LUA_SECTION_HEADER +
            VALID_P8_FOOTER))
        test_p8_path = os.path.join(self.tempdir, 'test.p8')
        file.to_file(g, test_p8_path)

        tg = file.from_file(test_p8_path)
        self.assertEqual(4, tg.lua._version)
        self.assertEqual(4, tg.gfx._version)
        self.assertEqual(4, tg.gff._version)
        self.assertEqual(4, tg.map._version)
        self.assertEqual(4, tg.sfx._version)
        self.assertEqual(4, tg.music._version)


class TestP8Include(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def testGetRootIncludePathMacOSCartRoot(self):
        cartpath = os.path.abspath(
            os.path.normpath(
                os.path.expanduser(
                    '~/Library/Application Support/'
                    'pico-8/carts/subdir/somecart.p8')))
        expected = os.path.abspath(
            os.path.normpath(
                os.path.expanduser(
                    '~/Library/Application Support/pico-8/carts')))
        self.assertEqual(
            expected,
            p8.get_root_include_path(cartpath))

    def testGetRootIncludePathLinuxCartRoot(self):
        cartpath = os.path.abspath(
            os.path.normpath(
                os.path.expanduser(
                    '~/.lexaloffle/pico-8/carts/subdir/somecart.p8')))
        expected = os.path.abspath(
            os.path.normpath(
                os.path.expanduser('~/.lexaloffle/pico-8/carts')))
        self.assertEqual(
            expected,
            p8.get_root_include_path(cartpath))

    def testGetRootIncludePathUnrecognizedRoot(self):
        cartpath = '/tmp/subdir/somecart.p8'
        expected = os.path.abspath('/tmp/subdir')
        self.assertEqual(
            expected,
            p8.get_root_include_path(cartpath))

    def testLinesForTabYieldsAll(self):
        lines = CODE_WITH_TABS.split(b'\n')
        result = list(p8.lines_for_tab(lines, None))
        self.assertEqual(result, lines)

    def testLinesForTabYieldsOneTab(self):
        lines = CODE_WITH_TABS.split(b'\n')
        expected = CODE_WITH_TABS_TAB_TWO.strip().split(b'\n')
        result = list(p8.lines_for_tab(lines, 2))
        self.assertEqual(expected, result)

    def assertP8CartCodeEquals(self, expected, filepath=None):
        test_cart_path = filepath or os.path.join(self.tempdir, 't.p8')
        with open(test_cart_path, 'rb') as fh:
            g = p8.P8Formatter.from_file(fh, filename=test_cart_path)
        self.assertEqual(expected, b''.join(list(g.lua.to_lines())))

    def testIncludeLua(self):
        with open(os.path.join(self.tempdir, 'inc.lua'), 'wb') as fh:
            fh.write(CODE_WITH_TABS.strip() + b'\n')
        make_test_cart_from_code(
            self.tempdir, 't.p8', CODE_WITH_INCLUDE_LUA)
        expected = make_expected_with_include(CODE_WITH_TABS)
        self.assertP8CartCodeEquals(expected)

    def testIncludeP8(self):
        make_test_cart_from_code(
            self.tempdir, 'inc.p8', CODE_WITH_TABS)
        make_test_cart_from_code(
            self.tempdir, 't.p8', CODE_WITH_INCLUDE_P8)
        expected = make_expected_with_include(CODE_WITH_TABS)
        self.assertP8CartCodeEquals(expected)

    def testIncludeP8Tab(self):
        make_test_cart_from_code(
            self.tempdir, 'inc.p8', CODE_WITH_TABS)
        make_test_cart_from_code(
            self.tempdir, 't.p8', CODE_WITH_INCLUDE_P8_TAB)
        expected = make_expected_with_include(CODE_WITH_TABS_TAB_TWO)
        self.assertP8CartCodeEquals(expected)

    def testIncludeP8PNG(self):
        make_test_cart_from_code(
            self.tempdir, 'inc.p8.png', CODE_WITH_TABS, is_p8png=True)
        make_test_cart_from_code(
            self.tempdir, 't.p8', CODE_WITH_INCLUDE_P8PNG)
        expected = make_expected_with_include(CODE_WITH_TABS)
        self.assertP8CartCodeEquals(expected)

    def testIncludeP8PNGTab(self):
        make_test_cart_from_code(
            self.tempdir, 'inc.p8.png', CODE_WITH_TABS, is_p8png=True)
        make_test_cart_from_code(
            self.tempdir, 't.p8', CODE_WITH_INCLUDE_P8PNG_TAB)
        expected = make_expected_with_include(CODE_WITH_TABS_TAB_TWO)
        self.assertP8CartCodeEquals(expected)

    def testIncludeLuaSubdir(self):
        os.makedirs(os.path.join(self.tempdir, 'subdir'))
        with open(os.path.join(self.tempdir, 'subdir', 'inc.lua'), 'wb') as fh:
            fh.write(CODE_WITH_TABS.strip() + b'\n')
        make_test_cart_from_code(
            self.tempdir, 't.p8', CODE_WITH_INCLUDE_LUA_SUBDIR)
        expected = make_expected_with_include(CODE_WITH_TABS)
        self.assertP8CartCodeEquals(expected)

    def testIncludeLuaParentDirFails(self):
        make_test_cart_from_code(
            self.tempdir, 't.p8', CODE_WITH_INCLUDE_LUA_PARENT_DIR)
        self.assertRaises(
            p8.P8IncludeOutsideOfAllowedDirectory,
            self.assertP8CartCodeEquals,
            b'')

    # TODO: test that parent dirs are allowed when in a subdir of a recognized
    # cart directory. We'd need a test-only override for the root path.
    # def testIncludeLuaParentDirSucceeds(self):
    #     make_test_cart_from_code(
    #         self.tempdir, 't.p8', CODE_WITH_INCLUDE_LUA_PARENT_DIR)


if __name__ == '__main__':
    unittest.main()
