#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.gff import gff


class TestGff(unittest.TestCase):
    def testGetFlags(self):
        g = gff.Gff.empty()
        g._data = bytearray([x for x in range(256)])
        for x in range(256):
            self.assertEqual(x, g.get_flags(x, gff.ALL))
        self.assertEqual(gff.RED, g.get_flags(1, gff.RED))
        self.assertEqual(0, g.get_flags(1, gff.ORANGE))
        self.assertEqual(gff.RED, g.get_flags(3, gff.RED))
        self.assertEqual(gff.ORANGE, g.get_flags(3, gff.ORANGE))
        self.assertEqual(gff.RED | gff.ORANGE,
                          g.get_flags(3, gff.RED | gff.ORANGE))
        self.assertEqual(gff.RED | gff.ORANGE,
                          g.get_flags(3, gff.ALL))

    def testSetFlags(self):
        g = gff.Gff.empty()
        g.set_flags(0, gff.RED | gff.BLUE | gff.PEACH)
        self.assertEqual(gff.RED | gff.BLUE | gff.PEACH,
                         g.get_flags(0, gff.ALL))
        self.assertEqual(gff.RED | gff.PEACH,
                         g.get_flags(0, gff.RED | gff.PEACH))

        g.set_flags(0, gff.ORANGE)
        self.assertEqual(gff.RED | gff.BLUE | gff.PEACH | gff.ORANGE,
                         g.get_flags(0, gff.ALL))
        self.assertEqual(gff.RED | gff.PEACH,
                         g.get_flags(0, gff.RED | gff.PEACH))

    def testClearFlags(self):
        g = gff.Gff.empty()
        g.set_flags(0, gff.RED | gff.BLUE | gff.PEACH)
        self.assertEqual(gff.RED | gff.BLUE | gff.PEACH,
                         g.get_flags(0, gff.ALL))
        g.clear_flags(0, gff.BLUE)
        self.assertEqual(gff.RED | gff.PEACH,
                         g.get_flags(0, gff.ALL))

    def testResetFlags(self):
        g = gff.Gff.empty()
        g.set_flags(0, gff.RED | gff.BLUE | gff.PEACH)
        self.assertEqual(gff.RED | gff.BLUE | gff.PEACH,
                         g.get_flags(0, gff.ALL))
        g.reset_flags(0, gff.BLUE)
        self.assertEqual(gff.BLUE,
                         g.get_flags(0, gff.ALL))

        
if __name__ == '__main__':
    unittest.main()
