#!/usr/bin/env python3

import io
import sys
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8 import util


class TestUtil(unittest.TestCase):
    def setUp(self):
        util._write_stream = io.StringIO()
        util._error_stream = io.StringIO()
        
    def tearDown(self):
        util._quiet = False
        util._write_stream = sys.stdout
        util._error_stream = sys.stderr

    def testWrite(self):
        s = 'test1'
        util.write(s)
        self.assertEqual(s, util._write_stream.getvalue())

    def testWriteQuiet(self):
        util.set_quiet(True)
        s = 'test2'
        util.write(s)
        self.assertEqual('', util._write_stream.getvalue())

    def testError(self):
        s = 'test3'
        util.error(s)
        self.assertEqual(s, util._error_stream.getvalue())

    def testErrorQuiet(self):
        s = 'test4'
        util.set_quiet(True)
        util.error(s)
        self.assertEqual(s, util._error_stream.getvalue())

    
if __name__ == '__main__':
    unittest.main()
