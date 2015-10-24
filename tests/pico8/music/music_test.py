#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.music import music


VALID_MUSIC_LINES = ['00 41424344\n'] * 64


class TestMusic(unittest.TestCase):
    def testFromLines(self):
        m = music.Music.from_lines(VALID_MUSIC_LINES, 4)
        self.assertEqual(b'\x41\x42\x43\x44' * 64, m._data)
        self.assertEqual(4, m._version)
        
    def testToLines(self):
        m = music.Music.from_lines(VALID_MUSIC_LINES, 4)
        self.assertEqual(list(m.to_lines()), VALID_MUSIC_LINES)

        
if __name__ == '__main__':
    unittest.main()
