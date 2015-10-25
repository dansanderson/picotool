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


if __name__ == '__main__':
    unittest.main()
