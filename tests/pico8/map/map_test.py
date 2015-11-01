#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.gfx import gfx
from pico8.map import map


class TestMap(unittest.TestCase):
    def testGetCell(self):
        m = map.Map.empty()
        m._data[0:128] = (b'\x00\x01\x02\x03\x04\x05\x06\x07'
                          b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f') * 8
        for i in range(16):
            for j in range(8):
                self.assertEqual(i, m.get_cell(i + 16 * j, 0))
        for i in range(16):
            for j in range(8):
                self.assertEqual(0, m.get_cell(i + 16 * j, 1))
                
    def testGetCellSharedMem(self):
        m = map.Map.empty()
        m._gfx = gfx.Gfx.empty()
        m._gfx._data[4096:4112] = (b'\x00\x01\x02\x03\x04\x05\x06\x07'
                                   b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f') * 8
        for i in range(16):
            self.assertEqual(i, m.get_cell(i, 32))

    def testSetCell(self):
        m = map.Map.empty()
        for i in range(16):
            for j in range(8):
                m.set_cell(i + 16 * j, 0, i)
        for i in range(16):
            for j in range(8):
                self.assertEqual(i, m.get_cell(i + 16 * j, 0))
        for i in range(16):
            for j in range(8):
                self.assertEqual(0, m.get_cell(i + 16 * j, 1))

    def testGetRectTiles(self):
        m = map.Map.empty()
        for i in range(16):
            for j in range(8):
                m.set_cell(i + 16 * j, 0, i)
        tile_rect = m.get_rect_tiles(2, 0, width=8, height=2)
        self.assertEqual(2, len(tile_rect))
        self.assertEqual(8, len(tile_rect[0]))
        self.assertEqual(bytearray(
            b'\x02\x03\x04\x05\x06\x07\x08\x09'),
                         tile_rect[0])
        self.assertEqual(bytearray(b'\x00') * 8, tile_rect[1])

    def testGetRectTilesOffEdge(self):
        m = map.Map.empty()
        for i in range(16):
            for j in range(8):
                m.set_cell(i + 16 * j, 0, i)
        tile_rect = m.get_rect_tiles(124, 0, width=8, height=2)
        self.assertEqual(2, len(tile_rect))
        self.assertEqual(8, len(tile_rect[0]))
        self.assertEqual(bytearray(
            b'\x0c\x0d\x0e\x0f\x00\x00\x00\x00'),
                         tile_rect[0])
        self.assertEqual(bytearray(b'\x00') * 8, tile_rect[1])

    def testGetRectSharedMem(self):
        m = map.Map.empty()
        m._gfx = gfx.Gfx.empty()
        m._gfx._data[4096:4112] = (b'\x00\x01\x02\x03\x04\x05\x06\x07'
                                   b'\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f') * 8
        tile_rect = m.get_rect_tiles(2, 32, width=8, height=2)
        self.assertEqual(2, len(tile_rect))
        self.assertEqual(8, len(tile_rect[0]))
        self.assertEqual(bytearray(
            b'\x02\x03\x04\x05\x06\x07\x08\x09'),
                         tile_rect[0])
        self.assertEqual(bytearray(b'\x00') * 8, tile_rect[1])

    def testSetRectTiles(self):
        m = map.Map.empty()
        m._gfx = gfx.Gfx.empty()
        m.set_rect_tiles([[1] * 4] * 3, 2, 3)
        result = m.get_rect_tiles(0, 0, width=7, height=7)
        self.assertEqual(
            [bytearray(b'\x00\x00\x00\x00\x00\x00\x00'),
             bytearray(b'\x00\x00\x00\x00\x00\x00\x00'),
             bytearray(b'\x00\x00\x00\x00\x00\x00\x00'),
             bytearray(b'\x00\x00\x01\x01\x01\x01\x00'),
             bytearray(b'\x00\x00\x01\x01\x01\x01\x00'),
             bytearray(b'\x00\x00\x01\x01\x01\x01\x00'),
             bytearray(b'\x00\x00\x00\x00\x00\x00\x00')], result)
        
    def testGetRectPixels(self):
        m = map.Map.empty()
        m._gfx = gfx.Gfx.empty()
        for i in range(16):
            m._gfx.set_sprite(i, [[i] * 8] * 8)
        for i in range(16):
            for j in range(8):
                m.set_cell(i + 16 * j, 0, i)
        pixels = m.get_rect_pixels(2, 0, width=3, height=2)
        self.assertEqual(16, len(pixels))
        self.assertEqual(24, len(pixels[0]))
        for i in range(0,8):
            self.assertEqual(bytearray(b'\x02' * 8 + b'\x03' * 8 + b'\x04' * 8),
                             pixels[i])
        for i in range(8,16):
            self.assertEqual(bytearray(b'\x00' * 24), pixels[i])

            
if __name__ == '__main__':
    unittest.main()
