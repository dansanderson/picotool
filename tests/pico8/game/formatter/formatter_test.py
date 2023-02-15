#!/usr/bin/env python3

import unittest

from pico8.game.formatter.p8 import P8Formatter
from pico8.game import game
from pico8.lua import lua
from io import BytesIO

class TestP8Formatter(unittest.TestCase):
	def testEmojisArePreservedThroughFormatting(self):
		lua_code = 'print(\"Hello Emoji 🅾️\")'
		lua_code_utf8_bytes = lua_code.encode('utf-8')
		emoji_bytes = '🅾️'.encode('utf-8')

		output_cart = game.Game.make_empty_game('dummy.p8')
		output_cart.lua = lua.Lua.from_lines([lua_code_utf8_bytes], version=8)
		
		cart_stream = BytesIO()

		formatter = P8Formatter()
		formatter.to_file(
			output_cart,
			cart_stream,
			lua_writer_cls = lua.LuaEchoWriter)

		cart_bytes = cart_stream.getvalue()

		assert(emoji_bytes in cart_bytes)
