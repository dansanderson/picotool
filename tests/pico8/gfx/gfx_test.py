#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.gfx import gfx


VALID_GFX_LINES = (['0123456789abcdef' + '0' * 112 + '\n'] +
                   ['0' * 128 + '\n'] * 127)


class TestGfx(unittest.TestCase):
    def testFromLines(self):
        # (Add extra newline for coverage of line filter.)
        g = gfx.Gfx.from_lines(VALID_GFX_LINES + ['\n'], 4)
        self.assertEqual(bytes.fromhex('1032547698badcfe'), g._data[:8])
        self.assertEqual(4, g._version)

    def testToLines(self):
        g = gfx.Gfx.from_lines(VALID_GFX_LINES, 4)
        self.assertEqual(list(g.to_lines()), VALID_GFX_LINES)

    def testGetSpriteEmpty(self):
        g = gfx.Gfx.empty()
        empty_tile = [bytearray(b'\x00' * 8)] * 8
        for i in range(256):
            self.assertEqual(empty_tile, g.get_sprite(i))
            
    def testGetSpriteValues(self):
        g = gfx.Gfx.empty()
        g._data[0:8] = b'\x10\x32\x54\x76\x98\xba\xdc\xfe'
        first_sprite = ([bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07')] +
                        [bytearray(b'\x00' * 8)] * 7)
        second_sprite = ([bytearray(b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f')] +
                         [bytearray(b'\x00' * 8)] * 7)
        self.assertEqual(first_sprite, g.get_sprite(0))
        self.assertEqual(second_sprite, g.get_sprite(1))

    def testGetLargeSprite(self):
        g = gfx.Gfx.empty()
        g._data[0:64] = b'\x10\x32\x54\x76\x98\xba\xdc\xfe' * 8
        sprite = ([bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07' +
                             b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f')] +
                  [bytearray(b'\x00' * 16)] * 15)
        self.assertEqual(sprite, g.get_sprite(0, 2, 2))

    def testGetLargeSpriteOffEdge(self):
        g = gfx.Gfx.empty()
        g._data[0:64] = b'\x10\x32\x54\x76\x98\xba\xdc\xfe' * 8
        sprite = ([bytearray(b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f' +
                             b'\x00\x00\x00\x00\x00\x00\x00\x00')] +
                  [bytearray(b'\x00' * 16)] * 15)
        self.assertEqual(sprite, g.get_sprite(15, 2, 2))

    def testSetSprite(self):
        g = gfx.Gfx.empty()
        sprite = ([[0, 1, 2, 3, 4, 5, 6, 7],
                   [8, 9, 10, 11, 12, 13, 14, 15]] +
                  [[0] * 8] * 6)
        g.set_sprite(0, sprite)
        self.assertEqual(bytearray(b'\x10\x32\x54\x76\x00\x00\x00\x00'),
                         g._data[0:8])
        self.assertEqual(bytearray(b'\x98\xba\xdc\xfe\x00\x00\x00\x00'),
                         g._data[64:72])

    def testSetSpriteByteArray(self):
        g = gfx.Gfx.empty()
        sprite = ([b'\x00\x01\x02\x03\x04\x05\x06\x07',
                   b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'] +
                  [b'\x00' * 8] * 6)
        g.set_sprite(0, sprite)
        self.assertEqual(bytearray(b'\x10\x32\x54\x76\x00\x00\x00\x00'),
                         g._data[0:8])
        self.assertEqual(bytearray(b'\x98\xba\xdc\xfe\x00\x00\x00\x00'),
                         g._data[64:72])

    def testSetSpriteOffset(self):
        g = gfx.Gfx.empty()
        sprite = ([[0, 1, 2, 3, 4, 5, 6, 7],
                   [8, 9, 10, 11, 12, 13, 14, 15]] +
                  [[0] * 8] * 6)
        g.set_sprite(0, sprite, tile_x_offset=1, tile_y_offset=1)
        self.assertEqual(bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00'),
                         g._data[0:8])
        self.assertEqual(bytearray(b'\x00\x21\x43\x65\x07\x00\x00\x00'),
                         g._data[64:72])
        self.assertEqual(bytearray(b'\x80\xa9\xcb\xed\x0f\x00\x00\x00'),
                         g._data[128:136])
        
    def testSetLargeSprite(self):
        g = gfx.Gfx.empty()
        sprite = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]] * 12
        g.set_sprite(0, sprite)
        self.assertEqual(bytearray(b'\x10\x32\x54\x76\x98\xba\x00\x00'),
                         g._data[64 * 11:64 * 11 + 8])
                  
    def testSetSpriteOffEdge(self):
        g = gfx.Gfx.empty()
        sprite = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]] * 12
        g.set_sprite(15, sprite)
        self.assertEqual(bytearray(b'\x10\x32\x54\x76'),
                         g._data[64 * 11 + 15 * 4:64 * 11 + 15 * 4 + 4])
        new_spr = g.get_sprite(15, 2, 2)
        print('DEBUG: new_spr={}'.format(new_spr))
        self.assertEqual(
            [bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07' +
                       b'\x00' * 8)] * 12 +
            [bytearray(b'\x00' * 16)] * 4,
            g.get_sprite(15, 2, 2))
        
    def testSetSpriteTransparency(self):
        g = gfx.Gfx.empty()
        g.set_sprite(0, [[1] * 8] * 8)
        g.set_sprite(0, [[2, 2, gfx.TRANSPARENT, gfx.TRANSPARENT,
                          2, 2, gfx.TRANSPARENT, gfx.TRANSPARENT]] * 8)
        new_spr = g.get_sprite(0)
        self.assertEqual([bytearray(b'\x02\x02\x01\x01\x02\x02\x01\x01')] * 8,
                         new_spr)

    def testSetSpriteTransparencyOffset(self):
        g = gfx.Gfx.empty()
        g.set_sprite(0, [[1] * 8] * 8)
        g.set_sprite(0, [[2, 2, gfx.TRANSPARENT, gfx.TRANSPARENT,
                          2, 2, gfx.TRANSPARENT, gfx.TRANSPARENT]] * 8,
                     3, 0)
        new_spr = g.get_sprite(0)
        self.assertEqual([bytearray(b'\x01\x01\x01\x02\x02\x01\x01\x02')] * 8,
                         new_spr)


if __name__ == '__main__':
    unittest.main()
