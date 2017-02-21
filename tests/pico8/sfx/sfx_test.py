#!/usr/bin/env python3

import os
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.game import game
from pico8.sfx import sfx


VALID_SFX_LINES = ([
    b'0110000000472004620c3400c34318470004311842500415003700c30500375183750c3000c3751f4730c375053720536211540114330c37524555247120c3730a470163521d07522375164120a211220252e315\n',
    b'01100000183732440518433394033c65539403185432b543184733940318433394033c655306053940339403184733940318423394033c655394031845321433184733940318473394033c655394033940339403\n',
    b'01100000247552775729755277552475527755297512775524755277552b755277552475527757297552775720755247572775524757207552475227755247522275526757297552675722752267522975526751\n',
    b'01100000001750c055003550c055001750c055003550c05500175180650c06518065001750c065003650c065051751106505365110650c17518075003650c0650a145160750a34516075111451d075113451d075\n',
    b'011000001b5771f55722537265171b5361f52622515265121b7771f76722757267471b7461f7362271522712185771b5571d53722517187361b7261d735227122454527537295252e5171d73514745227452e745\n',
    b'01100000275422754227542275422e5412e5452b7412b5422b5452b54224544245422754229541295422954224742277422e7422b7422b5422b5472954227542295422b742307422e5422e7472b547305462e742\n',
    b'0110000030555307652e5752b755295622e7722b752277622707227561297522b072295472774224042275421b4421b5451b5421b4421d542295471d442295422444624546245472444727546275462944729547\n',
    b'0110000000200002000020000200002000020000200002000020000200002000020000200002000020000200110171d117110171d227131211f227130371f2370f0411b1470f2471b35716051221571626722367\n',
    b'001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002e775000002e1752e075000002e1752e77500000\n',
] + [b'001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000\n'] * 55)


class TestSfx(unittest.TestCase):
    def testFromLines(self):
        s = sfx.Sfx.from_lines(VALID_SFX_LINES, 4)
        # (bytes.fromhex takes a text str.)
        self.assertEqual(bytes.fromhex('002f002dcc08cc38'), s._data[:8])
        self.assertEqual(bytes.fromhex('01100000d83e2451'), s._data[64:72])
        self.assertEqual(4, s._version)

    def testToLines(self):
        s = sfx.Sfx.from_lines(VALID_SFX_LINES, 4)
        self.assertEqual(list(s.to_lines()), VALID_SFX_LINES)

    def testSetNote(self):
        s = sfx.Sfx.empty(version=4)
        s.set_note(0, 0, pitch=1, waveform=2, volume=3, effect=4)
        self.assertEqual(b'\x81\x46', s._data[0:2])
        s.set_note(0, 1, pitch=1, waveform=2, volume=3, effect=4)
        self.assertEqual(b'\x81\x46', s._data[2:4])
        s.set_note(1, 0, pitch=1, waveform=2, volume=3, effect=4)
        self.assertEqual(b'\x81\x46', s._data[68:70])

    def testGetNote(self):
        s = sfx.Sfx.empty(version=4)
        s.set_note(0, 0, pitch=1, waveform=2, volume=3, effect=4)
        self.assertEqual((1, 2, 3, 4), s.get_note(0, 0))
        s.set_note(0, 1, pitch=1, waveform=2, volume=3, effect=4)
        self.assertEqual((1, 2, 3, 4), s.get_note(0, 1))
        s.set_note(1, 0, pitch=1, waveform=2, volume=3, effect=4)
        self.assertEqual((1, 2, 3, 4), s.get_note(1, 0))

    def testSetProperties(self):
        s = sfx.Sfx.empty(version=4)
        s.set_properties(0,
                         editor_mode=1, note_duration=2,
                         loop_start=3, loop_end=4)
        self.assertEqual(b'\x01\x02\x03\x04', s._data[64:68])
        s.set_properties(0, editor_mode=0)
        self.assertEqual(b'\x00\x02\x03\x04', s._data[64:68])
        s.set_properties(0, note_duration=255)
        self.assertEqual(b'\x00\xff\x03\x04', s._data[64:68])
        s.set_properties(0, loop_start=10)
        self.assertEqual(b'\x00\xff\x0a\x04', s._data[64:68])
        s.set_properties(0, loop_end=11)
        self.assertEqual(b'\x00\xff\x0a\x0b', s._data[64:68])

        s.set_properties(63,
                         editor_mode=1, note_duration=2,
                         loop_start=3, loop_end=4)
        self.assertEqual(b'\x01\x02\x03\x04', s._data[63 * 68 + 64:63 * 68 + 68])
        s.set_properties(63, editor_mode=0)
        self.assertEqual(b'\x00\x02\x03\x04', s._data[63 * 68 + 64:63 * 68 + 68])
        s.set_properties(63, note_duration=255)
        self.assertEqual(b'\x00\xff\x03\x04', s._data[63 * 68 + 64:63 * 68 + 68])
        s.set_properties(63, loop_start=10)
        self.assertEqual(b'\x00\xff\x0a\x04', s._data[63 * 68 + 64:63 * 68 + 68])
        s.set_properties(63, loop_end=11)
        self.assertEqual(b'\x00\xff\x0a\x0b', s._data[63 * 68 + 64:63 * 68 + 68])

    def testGetProperties(self):
        s = sfx.Sfx.empty(version=4)
        
        # (A Pico-8 default cart has a note duration of 1 for the first
        # pattern.)
        self.assertEqual((0, 1, 0, 0), s.get_properties(0))
        s.set_properties(0,
                         editor_mode=1, note_duration=2,
                         loop_start=3, loop_end=4)
        self.assertEqual((1, 2, 3, 4), s.get_properties(0))
        
        # (A Pico-8 default cart has a note duration of 16 for all other
        # patterns.)
        self.assertEqual((0, 16, 0, 0), s.get_properties(63))
        s.set_properties(63,
                         editor_mode=1, note_duration=2,
                         loop_start=3, loop_end=4)
        self.assertEqual((1, 2, 3, 4), s.get_properties(63))

    
class TestHelloWorld(unittest.TestCase):
    '''Tests to address a weird case where one sfx pattern in helloworld.p8.png
    was coming out slightly wrong.

    This discrepancy is probably due to an old Pico-8 bug about how
    helloworld.p8.png was originally produced, so I don't plan on
    fixing it. I'm leaving this test in for added coverage.
    '''
    
    def setUp(self):
        self.testdata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'testdata')

    def testPattern(self):
        # (bytes.fromhex takes a text str.)
        dataline = bytes.fromhex('d83e245118373931bc5b393158396b39183f393118373931bc5bb05139313931183f393118353931bc5b3931183b2137183f3931183f3931bc5b39313931393101100000')
        s = sfx.Sfx(data=(dataline * 64), version=4)
        l = list(s.to_lines())[0]
        self.assertEqual(b'01100000183732440518433394033c65539403185432b543184733940318433394033c655306053940339403184733940318423394033c655394031845321433184733940318473394033c655394033940339403\n', l)

    def testGame(self):
        with open(os.path.join(self.testdata_path, 'test_cart_memdump.p8.png'), 'rb') as fh:
            g = game.Game.from_p8png_file(fh)
        # (bytes.fromhex takes a text str.)
        dataline = bytes.fromhex('d83e245118373931bc5b393158396b39183f393118373931bc5bb05139313931183f393118353931bc5b3931183b2137183f3931183f3931bc5b39313931393101100000')
        self.assertEqual(dataline, g.sfx._data[68:136])
        l = list(g.sfx.to_lines())[1]
        self.assertEqual(b'01100000183732440518433394033c65539403185432b543184733940318433394033c655306053940339403184733940318423394033c655394031845321433184733940318473394033c655394033940339403\n', l)
        
        
if __name__ == '__main__':
    unittest.main()
