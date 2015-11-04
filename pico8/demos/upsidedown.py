"""The main routines for the upsidedown demo.

Limitations:

* spr / sspr drawing a rectangle tiles is not yet supported. To do
  this, we need to flip the entire spritesheet (not individual
  sprites), re-calculate sprite IDs on the map, and translate sprite
  ID arguments.

* print / cursor naturally prints left to right and right-side up, so
  the tool compromises and only adjusts the y coordinate. Any cart
  that relies on two consecutive positionless prints won't quite do
  the right thing.

* This increases the token count, so large carts can't be turned
  upside down. In many cases, the tool will succeed because picotool
  under-counts tokens, but the cart won't run when loaded into Pico-8.

And probably other shortcomings of the tool or the parser that I
haven't found yet.
"""

__all__ = ['main']

import argparse
import tempfile
import textwrap

from .. import util
from ..game import game
from ..lua import lexer
from ..lua import lua
from ..lua import parser


def _get_argparser():
    """Builds and returns the argument parser."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='%(prog)s [--help] [--smallmap] <in-filename> [<out-filename>]',
        description=textwrap.dedent('''
        Turns a Pico-8 cart upside down.

          p8upsidedown mycart.p8.png mycart_upsidedown.p8
        '''))
    parser.add_argument('--smallmap', action='store_true',
                        help='assume the cart\'s shared gfx/map region is used '
                        'as gfx; the default is to assume it is used as map')
    parser.add_argument('--flipbuttons', action='store_true',
                        help='switch buttons left and right, up and down')
    parser.add_argument('--flipsounds', action='store_true',
                        help='reverse sound effect patterns')
    parser.add_argument('infile', type=str,
                        help='the cart to turn upside down; can be .p8 '
                        'or .p8.png')
    parser.add_argument('outfile', type=str, nargs='?',
                        help='the filename of the new cart; must end in .p8; '
                        'if not specified, adds _upsidedown.p8 to the original '
                        'base name')
    return parser


class UpsideDownASTTransform(lua.BaseASTWalker):
    """Transforms Lua code to invert coordinates of drawing functions."""
    def __init__(self, *args, **kwargs):
        self._smallmap = None
        self._flipbuttons = None
        for argname in ['smallmap', 'flipbuttons']:
            if argname in kwargs:
                setattr(self, '_' + argname, kwargs[argname])
                del kwargs[argname]
        super().__init__(*args, **kwargs)
        
    def _make_binop(self, val_or_exp1, exp2, binop='-'):
        """Makes an ExpBinOp equivalent to maxval - exp.

        Args:
          val_or_exp1: a number or an expression node to be the left exp.
          exp2: an expression node to be the right exp.
          binop: a string representing the binary operator.

        Returns:
          The equivalent of ExpBinOp(val_or_exp1, binop, exp2).
        """
        if not isinstance(val_or_exp1, parser.Node):
            val_or_exp1 = parser.ExpValue(lexer.TokNumber(str(val_or_exp1)))
        exp2 = parser.ExpValue(exp2)
            
        return parser.ExpBinOp(val_or_exp1,
                               lexer.TokSymbol(binop),
                               exp2)
    
    def _walk_FunctionCall(self, node):
        if not isinstance(node.exp_prefix, parser.VarName):
            # upsidedown only supports directly named calls to graphics
            # functions.
            return
        func_name = node.exp_prefix.name.code

        if self._flipbuttons and (func_name == 'btn' or func_name == 'btnp'):
            # It's not too tricky to swap odds and evens in a Lua expression, but it'd be a pain to write out the AST
            # for it. So instead, we only support calls to btn/btnp where the first argument is a numeric constant,
            # so we can swap them statically.
            if isinstance(node.args.explist.exps[0].value, lexer.TokNumber):
                numval = int(node.args.explist.exps[0].value.code)
                if numval % 2 == 0:
                    numval += 1
                else:
                    numval -= 1
                node.args.explist.exps[0].value = lexer.TokNumber(str(numval))

        elif func_name == 'pget':
            # pget x y
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(127, node.args.explist.exps[1])
            
        elif func_name == 'pset':
            # pset x y [c]
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(127, node.args.explist.exps[1])
            
        elif func_name == 'sget':
            # sget x y
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(127 if self._smallmap else 63,
                                                         node.args.explist.exps[1])
            
        elif func_name == 'sset':
            # sset x y [c]
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(127 if self._smallmap else 63,
                                                         node.args.explist.exps[1])
            
        elif func_name == 'print':
            # print str [x y [col]]
            if len(node.args.explist.exps) > 1:
                # Printing is always left to right, so only invert the y
                # coordinate, and leave a line's worth of space.
                # (This is still insufficient for carts that use 'cursor' then
                # print more than one line.)
                node.args.explist.exps[2] = self._make_binop(119, node.args.explist.exps[2])
                
        elif func_name == 'cursor':
            # cursor x y
            node.args.explist.exps[1] = self._make_binop(119, node.args.explist.exps[1])

        elif func_name == 'camera':
            # camera [x y]
            if node.args.explist is not None:
                # Invert the sign of the camera offset.
                node.args.explist.exps[0] = self._make_binop(0, node.args.explist.exps[0])
                node.args.explist.exps[1] = self._make_binop(0, node.args.explist.exps[1])

        elif func_name == 'circ':
            # circ x y r [col]
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(127, node.args.explist.exps[1])
            
        elif func_name == 'circfill':
            # circfill x y r [col]
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(127, node.args.explist.exps[1])
            
        elif func_name == 'line':
            # line x0 y0 x1 y1 [col]
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(127, node.args.explist.exps[1])
            node.args.explist.exps[2] = self._make_binop(127, node.args.explist.exps[2])
            node.args.explist.exps[3] = self._make_binop(127, node.args.explist.exps[3])
            
        elif func_name == 'rect':
            # rect x0 y0 x1 y1 [col]
            # swap x0<->x1, y0<->y1
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[2])
            node.args.explist.exps[1] = self._make_binop(127, node.args.explist.exps[1])
            node.args.explist.exps[2] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[3] = self._make_binop(127, node.args.explist.exps[3])
            
        elif func_name == 'rectfill':
            # rectfill x0 y0 x1 y1 [col]
            # swap x0<->x1, y0<->y1
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[2])
            node.args.explist.exps[1] = self._make_binop(127, node.args.explist.exps[1])
            node.args.explist.exps[2] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[3] = self._make_binop(127, node.args.explist.exps[3])
            
        elif func_name == 'spr':
            # spr n x y [w h] [flip_x] [flip_y]
            if len(node.args.explist.exps) > 3:
                util.error('Unsupported: can\'t invert blitting more than one tile\n')
                # TODO: invert sprite sheet to support this
            # TODO: uh, not sure why this is needed to get Jelpi to look right. Why 113?
            node.args.explist.exps[1] = self._make_binop(113, node.args.explist.exps[1])
            node.args.explist.exps[2] = self._make_binop(113, node.args.explist.exps[2])
        
        elif func_name == 'sspr':
            # sspr sx sy sw sh dx dy [dw dh] [flip_x] [flip_y]
            util.error('Unsupported: can\'t invert sspr\n')
            # TODO: invert sprite sheet to support this
        
        elif func_name == 'mget':
            # mget x y
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(31 if self._smallmap else 63,
                                                         node.args.explist.exps[1])
            
        elif func_name == 'mset':
            # mset x y v
            node.args.explist.exps[0] = self._make_binop(127, node.args.explist.exps[0])
            node.args.explist.exps[1] = self._make_binop(31 if self._smallmap else 63, 
                                                         node.args.explist.exps[1])
            
        elif func_name == 'map' or func_name == 'mapdraw':
            # map cel_x cel_y sx sy cel_w cel_h [layer]
            cel_x = node.args.explist.exps[0]
            cel_y = node.args.explist.exps[1]
            sx = node.args.explist.exps[2]
            sy = node.args.explist.exps[3]
            cel_w = node.args.explist.exps[4]
            cel_h = node.args.explist.exps[5]

            # new cel_x = 128 - cel_x - cel_w
            cel_x = self._make_binop(self._make_binop(128, cel_x), cel_w)
            node.args.explist.exps[0] = cel_x
            
            # new cel_y = (32 or 64) - cel_y - cel_h
            cel_y = self._make_binop(self._make_binop(32 if self._smallmap else 64,
                                     cel_y), cel_h)
            node.args.explist.exps[1] = cel_y
            
            # new sx = 128 - sx - 8 * cel_w
            sx = self._make_binop(self._make_binop(
                128, sx), self._make_binop(8, cel_w, binop='*'))
            node.args.explist.exps[2] = sx
            
            # new sy = 128 - sy - 8 * cel_h
            sy = self._make_binop(self._make_binop(
                128, sy), self._make_binop(8, cel_h, binop='*'))
            node.args.explist.exps[3] = sy
            
        yield


def upsidedown_game(g, smallmap=False, flipbuttons=False, flipsounds=False):
    """Turn a game upside down.

    This modifies the game in-place.

    Args:
      g: The Game to turn upside down.
      smallmap: True if the gfx/map shared region is used as gfx, False
        otherwise.
      flipbuttons: If True, reverses functions regarding reading buttons
        to swap left and right, up and down.
      flipsounds: If True, reverses sound effect / music pattern data.
    """
    last_sprite = 256 if smallmap else 128
    for id in range(last_sprite):
        sprite = g.gfx.get_sprite(id)
        flipped_sprite = reversed(list(reversed(row) for row in sprite))
        g.gfx.set_sprite(id, flipped_sprite)

    last_map_row = 32 if smallmap else 64
    tile_rect = g.map.get_rect_tiles(0, 0, 128, last_map_row)
    flipped_map = reversed(list(reversed(row) for row in tile_rect))
    g.map.set_rect_tiles(flipped_map, 0, 0)

    if flipsounds:
        for id in range(63):
            notes = [g.sfx.get_note(id, n) for n in range(32)]
            notes.reverse()
            for n in range(32):
                g.sfx.set_note(id, n, *notes[n])
            (editor_mode, note_duration, loop_start, loop_end) = g.sfx.get_properties(id)
            if loop_start:
                g.sfx.set_properties(id, loop_start=63-loop_end)
            if loop_end:
                g.sfx.set_properties(id, loop_end=63-loop_start)

    transform = UpsideDownASTTransform(g.lua.tokens, g.lua.root,
                                       smallmap=smallmap,
                                       flipbuttons=flipbuttons)
    try:
        it = transform.walk()
        while True:
            it.__next__()
    except StopIteration:
        pass
    

def main(orig_args):
    arg_parser = _get_argparser()
    args = arg_parser.parse_args(args=orig_args)

    if args.outfile:
        if not args.outfile.endswith('.p8'):
            util.error('Filename {} must end in .p8\n'.format(args.outfile))
            return 1
        out_fname = args.outfile
    else:
        if args.infile.endswith('.p8'):
            basename = args.infile[:-len('.p8')]
        elif args.infile.endswith('.p8.png'):
            basename = args.infile[:-len('.p8.png')]
        else:
            util.error('Filename {} must end in .p8 or '
                       '.p8.png\n'.format(args.infile))
            return 1
        out_fname = basename + '_upsidedown.p8'

    g = game.Game.from_filename(args.infile)

    upsidedown_game(g, args.smallmap, args.flipbuttons, args.flipsounds)

    g.lua.reparse(writer_cls=lua.LuaASTEchoWriter, writer_args={'ignore_tokens': True})

    with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as outfh:
        g.to_p8_file(outfh, filename=out_fname,
                     lua_writer_cls=lua.LuaMinifyTokenWriter)
        outfh.seek(0)
        with open(out_fname, 'w', encoding='utf-8') as finalfh:
            finalfh.write(outfh.read())
            
    return 0
