"""The main routines for the command-line tool."""

__all__ = ['main']


import argparse
import csv
import os
import sys
import textwrap

from . import util
from .game import game
from .lua import lexer
from .lua import lua
from .lua import parser


def _get_argparser():
    """Builds and returns the argument parser."""
    # TODO: real help text
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''
        Commands:
          stats [--csv] <filename> [<filename>...]
            Display stats about one or more carts.
        '''))
    parser.add_argument(
        'command', type=str,
        help='the command to execute')
    parser.add_argument(
        '--indentwidth', type=int, action='store', default=2,
        help='the indent width as a number of spaces')
    parser.add_argument(
        '--overwrite', action='store_true',
        help='given a filename, overwrites the original file instead of '
        'creating a separate *_fmt.p8 file')
    parser.add_argument(
        '--minify', action='store_true',
        help='minifies the code instead of formatting it')
    parser.add_argument(
        '--csv', action='store_true',
        help='for stats, output a CSV file instead of text')
    parser.add_argument(
        '-q', '--quiet', action='store_true',
        help='suppresses inessential messages')
    parser.add_argument(
        '--debug', action='store_true',
        help='write extra error messages for debugging the tool')
    parser.add_argument(
        'filename', type=str, nargs='+',
        help='the names of files to process')

    return parser


def _games_for_filenames(filenames, print_tracebacks=False):
    """Yields games for the given filenames.

    If a file does not load or parse as a game, this writes a message
    to stderr and yields None. Processing of the argument list will
    continue if the caller continues.

    Args:
      filenames: The list of filenames.
      print_tracebacks: If True, prints a stack track along with lexer and
        parser error messages. (Useful for debugging the parser.) Default is
        False.

    Yields:
      (filename, game), or (filename, None) if the file did not parse.
    """
    for fname in filenames:
        if not fname.endswith('.p8.png') and not fname.endswith('.p8'):
            util.error('{}: filename must end in .p8 or .p8.png\n'.format(fname))
            continue

        g = None
        try:
            g = game.Game.from_filename(fname)
        except lexer.LexerError as e:
            util.error('{}: {}\n'.format(fname, e))
            yield (fname, None)
        except parser.ParserError as e:
            util.error('{}: {}\n'.format(fname, e))
            if print_tracebacks:
                import traceback
                traceback.print_exc(file=util._error_stream)
            yield (fname, None)
        else:
            yield (fname, g)


def stats(args):
    """Run the stats tool.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    csv_writer = None
    if args.csv:
        csv_writer = csv.writer(sys.stdout)
        csv_writer.writerow([
            'Filename',
            'Title',
            'Byline',
            'Code Version',
            'Char Count',
            'Token Count',
            'Line Count',
            'Compressed Code Size'
        ])

    for fname, g in _games_for_filenames(args.filename,
                                         print_tracebacks=args.debug):
        if g is None:
            util.error('{}: could not load cart'.format(fname))
            continue
        
        if args.csv:
            csv_writer.writerow([
                os.path.basename(fname),
                g.lua.get_title(),
                g.lua.get_byline(),
                g.lua.version,
                g.lua.get_char_count(),
                g.lua.get_token_count(),
                g.lua.get_line_count(),
                g.compressed_size
            ])
        else:
            title = g.lua.get_title()
            byline = g.lua.get_byline()
                
            if title is not None:
                util.write('{} ({})\n'.format(
                    title, os.path.basename(g.filename)))
            else:
                util.write(os.path.basename(g.filename) + '\n')
            if byline is not None:
                util.write(byline + '\n')
            util.write('- version: {}\n- lines: {}\n- chars: {}\n'
                       '- tokens: {}\n- compressed chars: {}\n'.format(
                g.lua.version, g.lua.get_line_count(),
                g.lua.get_char_count(), g.lua.get_token_count(),
                g.compressed_size if g.compressed_size is not None else '(not compressed)'))
            util.write('\n')

    return 0


def listlua(args):
    """Run the listlua tool.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename,
                                         print_tracebacks=args.debug):
        if len(args.filename) > 1:
            util.write('=== {} ===\n'.format(g.filename))
        for l in g.lua.to_lines():
            util.write(l)
        util.write('\n')
        
    return 0


def listtokens(args):
    """Run the listlua tool.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename,
                                         print_tracebacks=args.debug):
        if len(args.filename) > 1:
            util.write('=== {} ===\n'.format(g.filename))
        pos = 0
        for t in g.lua.tokens:
            if isinstance(t, lexer.TokNewline):
                util.write('\n')
            elif (isinstance(t, lexer.TokSpace) or isinstance(t, lexer.TokComment)):
                util.write('<{}>'.format(t.value))
            else:
                util.write('<{}:{}>'.format(pos, t.value))
                pos += 1
        util.write('\n')
    return 0


def writep8(args):
    """Writes the game to a .p8 file.

    If the original was a .p8.png file, this converts it to a .p8 file.

    If the original was a .p8 file, this just echos the game data into a new
    file. (This is mostly useful to validate the picotool library.)

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename,
                                         print_tracebacks=args.debug):
        if args.overwrite and fname.endswith('.p8'):
            out_fname = fname
        else:
            if fname.endswith('.p8.png'):
                out_fname = fname[:-len('.p8.png')] + '_fmt.p8'
            else:
                out_fname = fname[:-len('.p8')] + '_fmt.p8'

        with open(out_fname, 'w') as fh:
            g.to_p8_file(fh, filename=out_fname)
            
    return 0


def luamin(args):
    """Reduces the Lua code for a cart to use a minimal number of characters.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename,
                                         print_tracebacks=args.debug):
        if args.overwrite and fname.endswith('.p8'):
            out_fname = fname
        else:
            if fname.endswith('.p8.png'):
                out_fname = fname[:-len('.p8.png')] + '_fmt.p8'
            else:
                out_fname = fname[:-len('.p8')] + '_fmt.p8'

        with open(out_fname, 'w') as fh:
            g.to_p8_file(fh, filename=out_fname,
                         lua_writer_cls=lua.LuaMinifyWriter)
            
    return 0


def luafmt(args):
    """Rewrite the Lua code for a cart to use regular formatting.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename,
                                         print_tracebacks=args.debug):
        if args.overwrite and fname.endswith('.p8'):
            out_fname = fname
        else:
            if fname.endswith('.p8.png'):
                out_fname = fname[:-len('.p8.png')] + '_fmt.p8'
            else:
                out_fname = fname[:-len('.p8')] + '_fmt.p8'

        with open(out_fname, 'w') as fh:
            g.to_p8_file(fh, filename=out_fname,
                         lua_writer_cls=lua.LuaFormatterWriter)
            
    return 0


_PRINTAST_INDENT_SIZE = 2
def _printast_node(value, indent=0, prefix=''):
    """Recursive procedure for printast.

    Args:
      value: An element from the AST: a Node, a list, or a tuple.
      indent: The indentation level for this value.
      prefix: A string prefix for this value.
    """
    if isinstance(value, parser.Node):
        util.write('{}{}{}\n'.format(' ' * indent, prefix,
                                     value.__class__.__name__))
        for field in value._fields:
            _printast_node(getattr(value, field),
                           indent=indent+_PRINTAST_INDENT_SIZE,
                           prefix='* {}: '.format(field))
    elif isinstance(value, list) or isinstance(value, tuple):
        util.write('{}{}[list:]\n'.format(' ' * indent, prefix))
        for item in value:
            _printast_node(item,
                           indent=indent+_PRINTAST_INDENT_SIZE,
                           prefix='- ')
    else:
        util.write('{}{}{}\n'.format(' ' * indent, prefix, value))    

        
def printast(args):
    """Prints the parser's internal representation of Lua code.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename,
                                         print_tracebacks=args.debug):
        if len(args.filename) > 1:
            util.write('=== {} ===\n'.format(g.filename))
        _printast_node(g.lua.root)
    return 0


def main(orig_args):
    arg_parser = _get_argparser()
    args = arg_parser.parse_args(args=orig_args)
    util.set_quiet(args.quiet)

    if args.command == 'stats':
        return stats(args)
    elif args.command == 'listlua':
        return listlua(args)
    elif args.command == 'listtokens':
        return listtokens(args)
    elif args.command == 'printast':
        return printast(args)
    elif args.command == 'writep8':
        return writep8(args)
    elif args.command == 'luamin':
        return luamin(args)
    elif args.command == 'luafmt':
        return luafmt(args)
    
    arg_parser.print_help()
    return 1
