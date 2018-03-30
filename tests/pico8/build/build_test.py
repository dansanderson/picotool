#!/usr/bin/env python3

import argparse
import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.build import build
from pico8.game import game
from pico8.lua import lua


class TestDoBuild(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.tempdir)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tempdir)

    def testErrorOutputFilenameHasWrongExtension(self):
        args = argparse.Namespace(filename='foo.xxx')
        self.assertEqual(1, build.do_build(args))

    def testErrorInputFileDoesNotExist(self):
        args = argparse.Namespace(lua='doesnotexist.p8', filename='foo.p8')
        self.assertEqual(1, build.do_build(args))

    def testErrorInputFileHasWrongExtension(self):
        open('in.xxx', 'wb').close()
        self.assertTrue(os.path.exists('in.xxx'))
        args = argparse.Namespace(lua='in.xxx', filename='foo.p8')
        self.assertEqual(1, build.do_build(args))

    def testErrorBothInputAndEmptyArgsSpecified(self):
        open('in.p8', 'wb').close()
        self.assertTrue(os.path.exists('in.p8'))
        args = argparse.Namespace(lua='in.p8', empty_lua=True,
                                  filename='foo.p8')
        self.assertEqual(1, build.do_build(args))

    def testBuildCreatesEmptyDefault(self):
        args = argparse.Namespace(filename='foo.p8')
        self.assertEqual(0, build.do_build(args))
        self.assertTrue(os.path.exists('foo.p8'))
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__gfx__\n00000000', txt)

    def testBuildOverwritesExisting(self):
        output_cart = game.Game.make_empty_game('foo.p8')
        output_cart.gfx.set_sprite(0, [[1, 0, 1], [0, 1, 0], [1, 0, 1]])
        output_cart.gff.set_flags(0, 7)
        with open('foo.p8', 'wb') as outfh:
            output_cart.to_p8_file(outfh, filename='foo.p8')
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__gfx__\n10100000', txt)
            self.assertIn(b'__gff__\n07000000', txt)

        input_cart = game.Game.make_empty_game('in.p8')
        input_cart.gfx.set_sprite(0, [[2, 0, 2], [0, 2, 0], [2, 0, 2]])
        with open('in.p8', 'wb') as outfh:
            input_cart.to_p8_file(outfh, filename='in.p8')
        args = argparse.Namespace(gfx='in.p8', filename='foo.p8')
        self.assertEqual(0, build.do_build(args))
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__gfx__\n20200000', txt)
            self.assertIn(b'__gff__\n07000000', txt)

    def testBuildLuaFromP8(self):
        output_cart = game.Game.make_empty_game('foo.p8')
        output_cart.lua = lua.Lua.from_lines([b'print("zzz")'], version=8)
        with open('foo.p8', 'wb') as outfh:
            output_cart.to_p8_file(outfh, filename='foo.p8')
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__lua__\nprint("zzz")\n', txt)

        input_cart = game.Game.make_empty_game('in.p8')
        input_cart.lua = lua.Lua.from_lines([b'print("hi")'], version=8)
        with open('in.p8', 'wb') as outfh:
            input_cart.to_p8_file(outfh, filename='in.p8')
        args = argparse.Namespace(lua='in.p8', filename='foo.p8')
        self.assertEqual(0, build.do_build(args))
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__lua__\nprint("hi")\n', txt)

    def testBuildLuaFromLuaFile(self):
        output_cart = game.Game.make_empty_game('foo.p8')
        output_cart.lua = lua.Lua.from_lines([b'print("zzz")'], version=8)
        with open('foo.p8', 'wb') as outfh:
            output_cart.to_p8_file(outfh, filename='foo.p8')
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__lua__\nprint("zzz")\n', txt)

        with open('in.lua', 'wb') as outfh:
            outfh.write(b'print("hi")')
        args = argparse.Namespace(lua='in.lua', filename='foo.p8')
        self.assertEqual(0, build.do_build(args))
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__lua__\nprint("hi")\n', txt)

    def testBuildEmptiesSection(self):
        output_cart = game.Game.make_empty_game('foo.p8')
        output_cart.gfx.set_sprite(0, [[1, 0, 1], [0, 1, 0], [1, 0, 1]])
        output_cart.gff.set_flags(0, 7)
        with open('foo.p8', 'wb') as outfh:
            output_cart.to_p8_file(outfh, filename='foo.p8')
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__gfx__\n10100000', txt)
            self.assertIn(b'__gff__\n07000000', txt)

        args = argparse.Namespace(empty_gfx=True, filename='foo.p8')
        self.assertEqual(0, build.do_build(args))
        with open('foo.p8', 'rb') as infh:
            txt = infh.read()
            self.assertIn(b'__gfx__\n00000000', txt)
            self.assertIn(b'__gff__\n07000000', txt)


if __name__ == '__main__':
    unittest.main()
