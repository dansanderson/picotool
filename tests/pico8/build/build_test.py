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
from pico8.lua import lexer
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

    def testLocateRequireFileDefaultLuaPath(self):
        srcpath = os.path.join(self.tempdir, 'src.lua')
        filepath = os.path.join(self.tempdir, 'foo.lua')
        with open(filepath, 'wb') as outfh:
            outfh.write(b'-- hi')
        self.assertEqual(filepath, build._locate_require_file('foo', srcpath))
        self.assertEqual(filepath, build._locate_require_file('foo.lua', srcpath))

    def testLocateRequireFileCustomLuaPath(self):
        srcpath = os.path.join(self.tempdir, 'src.lua')
        os.makedirs(os.path.join(self.tempdir, 'bar'))
        filepath = os.path.join(self.tempdir, 'bar', 'foo.lua')
        with open(filepath, 'wb') as outfh:
            outfh.write(b'-- hi')
        self.assertEqual(
            filepath,
            build._locate_require_file(
                'foo', srcpath, lua_path='bar/?.lua;?;?.lua'))
        self.assertEqual(
            filepath,
            build._locate_require_file(
                'foo', srcpath, lua_path=self.tempdir + '/bar/?.lua;?;?.lua'))

    def testLocateRequireFileNotFound(self):
        srcpath = os.path.join(self.tempdir, 'src.lua')
        self.assertIsNone(build._locate_require_file('foo', srcpath))


class TestRequireWalker(unittest.TestCase):
    def testRequireWalkerNoRequires(self):
        ast = lua.Lua.from_lines([
            b'print("hi")',
            b'x = 7\n'], 8)
        result = list(build.RequireWalker(ast.tokens, ast.root).walk())
        self.assertEquals(0, len(result))

    def testRequireWalkerOneRequire(self):
        ast = lua.Lua.from_lines([
            b'print("hi")',
            b'require("foo")',
            b'x = 7\n'], 8)
        result = list(build.RequireWalker(ast.tokens, ast.root).walk())
        self.assertEquals(1, len(result))
        self.assertEquals((b'foo', False, lexer.TokSymbol(b'(')), result[0])

    def testRequireWalkerExpression(self):
        ast = lua.Lua.from_lines([
            b'print("hi")',
            b'foomod = require("foo")',
            b'x = 7\n'], 8)
        result = list(build.RequireWalker(ast.tokens, ast.root).walk())
        self.assertEquals(1, len(result))
        self.assertEquals((b'foo', False, lexer.TokSymbol(b'(')), result[0])

    def testRequireWalkerOptionsTable(self):
        ast = lua.Lua.from_lines([
            b'print("hi")',
            b'require("foo", {use_game_loop=true})',
            b'x = 7\n'], 8)
        result = list(build.RequireWalker(ast.tokens, ast.root).walk())
        self.assertEquals(1, len(result))
        self.assertEquals((b'foo', True, lexer.TokSymbol(b'(')), result[0])

    def testRequireWalkerComplexRequires(self):
        ast = lua.Lua.from_lines([
            b'foomod = require("foo")'
            b'function bar()',
            b'  require("foo", {use_game_loop=true})',
            b'end\n'], 8)
        result = list(build.RequireWalker(ast.tokens, ast.root).walk())
        self.assertEquals(2, len(result))

    def testRequireWalkerErrorZeroArgs(self):
        ast = lua.Lua.from_lines([b'require()'], 8)
        try:
            unused_result = list(build.RequireWalker(ast.tokens, ast.root).walk())
            self.fail()
        except build.LuaBuildError:
            pass

    def testRequireWalkerErrorFirstNonString(self):
        ast = lua.Lua.from_lines([b'require(123)'], 8)
        try:
            unused_result = list(build.RequireWalker(ast.tokens, ast.root).walk())
            self.fail()
        except build.LuaBuildError:
            pass

    def testRequireWalkerErrorSecondNonTable(self):
        ast = lua.Lua.from_lines([b'require("foo", 123)'], 8)
        try:
            unused_result = list(build.RequireWalker(ast.tokens, ast.root).walk())
            self.fail()
        except build.LuaBuildError:
            pass

    def testRequireWalkerErrorBadOptionName(self):
        ast = lua.Lua.from_lines([b'require("foo", {invalid_name=true})'], 8)
        try:
            unused_result = list(build.RequireWalker(ast.tokens, ast.root).walk())
            self.fail()
        except build.LuaBuildError:
            pass

    def testRequireWalkerErrorBadOptionValue(self):
        ast = lua.Lua.from_lines([b'require("foo", {use_game_loop=123})'], 8)
        try:
            unused_result = list(build.RequireWalker(ast.tokens, ast.root).walk())
            self.fail()
        except build.LuaBuildError:
            pass


class TestEvaluateRequire(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tempdir, 'bar'))
        self.file_path = os.path.join(self.tempdir, 'bar', 'foo.lua')

        self.lib1_file_path = os.path.join(self.tempdir, 'bar', 'lib1.lua')
        with open(self.lib1_file_path, 'wb') as outfh:
            outfh.write(b'x=1\nreturn 111\n')

        self.lib2_file_path = os.path.join(self.tempdir, 'bar', 'lib2.lua')
        with open(self.lib2_file_path, 'wb') as outfh:
            outfh.write(b'require("lib1")\nx=2\nreturn 222\n')

        self.lib3_file_path = os.path.join(self.tempdir, 'bar', 'lib3.lua')
        with open(self.lib3_file_path, 'wb') as outfh:
            outfh.write(b'x=3\nfunction _update60() end\nfunction _draw() end\n')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def testRequiresFile(self):
        ast = lua.Lua.from_lines([b'require("lib1")\n'], 8)
        package_lua = {}
        build.evaluate_require(ast, file_path=self.file_path, package_lua=package_lua)
        self.assertIn(b'lib1', package_lua)
        self.assertIn(b'x=1', b'\n'.join(package_lua[b'lib1'].to_lines()))

    def testRequiresInnerFile(self):
        ast = lua.Lua.from_lines([b'require("lib2")\n'], 8)
        package_lua = {}
        build.evaluate_require(ast, file_path=self.file_path, package_lua=package_lua)
        self.assertIn(b'lib1', package_lua)
        self.assertIn(b'x=1', b'\n'.join(package_lua[b'lib1'].to_lines()))
        self.assertIn(b'lib2', package_lua)
        self.assertIn(b'x=2', b'\n'.join(package_lua[b'lib2'].to_lines()))

    def testStripsGameLoop(self):
        ast = lua.Lua.from_lines([b'require("lib3")\n'], 8)
        package_lua = {}
        build.evaluate_require(ast, file_path=self.file_path, package_lua=package_lua)
        self.assertIn(b'lib3', package_lua)
        self.assertIn(b'x=3', b'\n'.join(package_lua[b'lib3'].to_lines()))
        self.assertNotIn(b'_update60', b'\n'.join(package_lua[b'lib3'].to_lines()))

    def testDoesntStripGameLoopOption(self):
        ast = lua.Lua.from_lines([b'require("lib3", {use_game_loop=true})\n'], 8)
        package_lua = {}
        build.evaluate_require(ast, file_path=self.file_path, package_lua=package_lua)
        self.assertIn(b'lib3', package_lua)
        self.assertIn(b'x=3', b'\n'.join(package_lua[b'lib3'].to_lines()))
        self.assertIn(b'_update60', b'\n'.join(package_lua[b'lib3'].to_lines()))

    def testErrorRequireNotFound(self):
        ast = lua.Lua.from_lines([b'require("not_found")\n'], 8)
        package_lua = {}
        self.assertRaises(
            build.LuaBuildError,
            build.evaluate_require,
            ast, file_path=self.file_path, package_lua=package_lua)

    def testErrorRelativePathChars(self):
        ast = lua.Lua.from_lines([b'require("../bar/lib1")\n'], 8)
        package_lua = {}
        self.assertRaises(
            build.LuaBuildError,
            build.evaluate_require,
            ast, file_path=self.file_path, package_lua=package_lua)


class TestPrependPackageLua(unittest.TestCase):
    def testEmptyPackageLua(self):
        ast = lua.Lua.from_lines([b'x=1\n'], 8)
        package_lua = {}
        self.assertEqual(ast, build._prepend_package_lua(ast, package_lua))

    def testPrependsCorrectPreamble(self):
        ast = lua.Lua.from_lines([b'require("lib1")\nx=2\n'], 8)
        package_lua = {b'lib1': lua.Lua.from_lines([b'x=3\n'], 8)}
        new_ast = build._prepend_package_lua(ast, package_lua)
        new_lines = b''.join(new_ast.to_lines())
        self.assertIn(b'package={', new_lines)
        self.assertIn(b'function()\nx=3\nend\n', new_lines)
        self.assertIn(b'function require(p)', new_lines)


if __name__ == '__main__':
    unittest.main()
