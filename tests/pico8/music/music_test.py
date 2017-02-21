#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.music import music


VALID_MUSIC_LINES = [b'00 41424344\n'] * 64


class TestMusic(unittest.TestCase):
    def testFromLines(self):
        m = music.Music.from_lines(VALID_MUSIC_LINES, 4)
        self.assertEqual(b'\x41\x42\x43\x44' * 64, m._data)
        self.assertEqual(4, m._version)
        
    def testToLines(self):
        m = music.Music.from_lines(VALID_MUSIC_LINES, 4)
        self.assertEqual(list(m.to_lines()), VALID_MUSIC_LINES)

    def testSetChannel(self):
        m = music.Music.empty(version=4)
        m.set_channel(0, 0, 0)
        self.assertEqual(b'\x00\x42\x43\x44', m._data[0:4])
        m.set_channel(0, 1, 1)
        self.assertEqual(b'\x00\x01\x43\x44', m._data[0:4])
        m.set_channel(0, 2, 2)
        self.assertEqual(b'\x00\x01\x02\x44', m._data[0:4])
        m.set_channel(0, 3, 3)
        self.assertEqual(b'\x00\x01\x02\x03', m._data[0:4])
        m.set_channel(1, 0, 0)
        self.assertEqual(b'\x00\x42\x43\x44', m._data[4:8])

        m.set_channel(0, 0, None)
        m.set_channel(0, 1, None)
        m.set_channel(0, 2, None)
        m.set_channel(0, 3, None)
        self.assertEqual(b'\x41\x42\x43\x44', m._data[0:4])

    def testGetChannel(self):
        m = music.Music.empty(version=4)
        self.assertIsNone(m.get_channel(0, 0))
        m.set_channel(0, 0, 0)
        self.assertEqual(0, m.get_channel(0, 0))
        self.assertIsNone(m.get_channel(0, 1))
        m.set_channel(0, 1, 1)
        self.assertEqual(1, m.get_channel(0, 1))
        self.assertIsNone(m.get_channel(0, 2))
        m.set_channel(0, 2, 2)
        self.assertEqual(2, m.get_channel(0, 2))
        self.assertIsNone(m.get_channel(0, 3))
        m.set_channel(0, 3, 3)
        self.assertEqual(3, m.get_channel(0, 3))
        self.assertIsNone(m.get_channel(1, 0))
        m.set_channel(1, 0, 0)
        self.assertEqual(0, m.get_channel(1, 0))
        
    def testSetProperties(self):
        m = music.Music.empty(version=4)
        m.set_channel(0, 0, 0)
        m.set_channel(0, 1, 1)
        m.set_channel(0, 2, 2)
        m.set_channel(0, 3, 3)
        self.assertEqual(b'\x00\x01\x02\x03', m._data[0:4])
        m.set_properties(0)
        self.assertEqual(b'\x00\x01\x02\x03', m._data[0:4])
        m.set_properties(0, begin=True)
        self.assertEqual(b'\x80\x01\x02\x03', m._data[0:4])
        m.set_properties(0, end=True)
        self.assertEqual(b'\x80\x81\x02\x03', m._data[0:4])
        m.set_properties(0, stop=True)
        self.assertEqual(b'\x80\x81\x82\x03', m._data[0:4])
        m.set_properties(0, begin=False, stop=False)
        self.assertEqual(b'\x00\x81\x02\x03', m._data[0:4])
        m.set_properties(0, begin=True, end=False)
        self.assertEqual(b'\x80\x01\x02\x03', m._data[0:4])

        m.set_channel(1, 0, 0)
        m.set_channel(1, 1, 1)
        m.set_channel(1, 2, 2)
        m.set_channel(1, 3, 3)
        self.assertEqual(b'\x00\x01\x02\x03', m._data[4:8])
        m.set_properties(1, begin=True)
        self.assertEqual(b'\x80\x01\x02\x03', m._data[4:8])

    def testGetProperties(self):
        m = music.Music.empty(version=4)
        self.assertEqual((False, False, False), m.get_properties(0))
        m.set_properties(0, begin=True)
        self.assertEqual((True, False, False), m.get_properties(0))
        m.set_properties(0, end=True)
        self.assertEqual((True, True, False), m.get_properties(0))
        m.set_properties(0, stop=True)
        self.assertEqual((True, True, True), m.get_properties(0))
        m.set_properties(0, begin=False, stop=False)
        self.assertEqual((False, True, False), m.get_properties(0))

    
if __name__ == '__main__':
    unittest.main()
