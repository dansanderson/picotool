"""The main routines for the command-line tool."""

__all__ = ['main']


import argparse
import csv
import os
import re
import sys
import tempfile
import textwrap
import traceback

from . import util
from .game import game
from .lua import lexer
from .lua import lua
from .lua import parser


def _get_argparser():
    """Builds and returns the argument parser."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='%(prog)s [--help] <command> [<args>] <filename> '
        '[<filename> ...]',
        description=textwrap.dedent('''
        Commands:
          stats [--csv] <filename> [<filename>...]
            Display stats about one or more carts.
          listlua <filename> [<filename>...]
            List the Lua code for a cart to the console.
          writep8 <filename> [<filename>...]
            Convert a .p8.png cart to a .p8 cart.
          luamin <filename> [<filename>...]
            Minify the Lua code for a cart, reducing the character count.
          luafmt [--overwrite] [--indentwidth=2] <filename> [<filename>...]
            Make the Lua code for a cart easier to read by adjusting indentation.
          luafind [--listfiles] <pattern> <filename> [<filename>...]
            Find a string or pattern in the code of one or more carts.

          listtokens <filename> [<filename>...]
            List the tokens for a cart to the console (for debugging picotool).
          printast <filename> [<filename>...]
            Print the picotool parser tree to the console (for debugging picotool).

          By default, commands that write to files (writep8, luamin,
          luafmt) will create or replace a file named similar to the
          cart filename but ending in "_fmt.p8". The luafmt command
          accepts an optional --overwrite argument that causes it to
          overwrite the original .p8 file instead.
        '''))
    parser.add_argument(
        'command', type=str,
        help='the command to execute')
    parser.add_argument(
        '--indentwidth', type=int, action='store', default=2,
        help='for luafmt, the indent width as a number of spaces')
    parser.add_argument(
        '--overwrite', action='store_true',
        help='for luafmt, given a filename, overwrites the original file '
        'instead of creating a separate *_fmt.p8 file')
    parser.add_argument(
        '--csv', action='store_true',
        help='for stats, output a CSV file instead of text')
    parser.add_argument(
        '--listfiles', action='store_true',
        help='for luafind, only list filenames, do not print matching lines')
    parser.add_argument(
        '-q', '--quiet', action='store_true',
        help='suppresses inessential messages')
    parser.add_argument(
        '--debug', action='store_true',
        help='write extra messages for debugging the tool')
    parser.add_argument(
        'filename', type=str, nargs='+',
        help='the names of files to process')

    return parser


def _games_for_filenames(filenames):
    """Yields games for the given filenames.

    If a file does not load or parse as a game, this writes a message
    to stderr and yields None. Processing of the argument list will
    continue if the caller continues.

    Args:
      filenames: The list of filenames.

    Yields:
      (filename, game), or (filename, None) if the file did not parse.
    """
    for fname in filenames:
        if not fname.endswith('.p8.png') and not fname.endswith('.p8'):
            util.error('{}: filename must end in .p8 or .p8.png\n'.format(
                fname))
            continue

        g = None
        try:
            g = game.Game.from_filename(fname)
        except lexer.LexerError as e:
            util.error('{}: {}\n'.format(fname, e))
            util.debug(traceback.format_exc())
            yield (fname, None)
        except parser.ParserError as e:
            util.error('{}: {}\n'.format(fname, e))
            util.debug(traceback.format_exc())
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

    for fname, g in _games_for_filenames(args.filename):
        if g is None:
            util.error('{}: could not load cart\n'.format(fname))
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
                g.compressed_size if g.compressed_size is not None
                           else '(not compressed)'))
            util.write('\n')

    return 0


def listlua(args):
    """Run the listlua tool.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename):
        if len(args.filename) > 1:
            util.write('=== {} ===\n'.format(g.filename))
        for l in g.lua.to_lines():
            try:
                util.write(l)
            except UnicodeEncodeError as e:
                new_l = ''.join(c if ord(c) < 128 else '_' for c in l)
                util.write(new_l)
        util.write('\n')
        
    return 0


def listtokens(args):
    """Run the listlua tool.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    for fname, g in _games_for_filenames(args.filename):
        if len(args.filename) > 1:
            util.write('=== {} ===\n'.format(g.filename))
        pos = 0
        for t in g.lua.tokens:
            if isinstance(t, lexer.TokNewline):
                util.write('\n')
            elif (isinstance(t, lexer.TokSpace) or
                  isinstance(t, lexer.TokComment)):
                util.write('<{}>'.format(t.value))
            else:
                util.write('<{}:{}>'.format(pos, t.value))
                pos += 1
        util.write('\n')
    return 0


def process_game_files(filenames, procfunc, overwrite=False, args=None):
    """Processes cart files in a common way.

    Args:
      filenames: The cart filenames as input.
      procfunc: A function called for each cart. This is called with arguments:
        a Game, an output stream, an output filename, and an argparse args
        object.
      overwrite: If True, overwrites the input file instead of making a _fmt.p8
        file, if the input file is a .p8 file.
      args: The argparse parsed args.

    Returns:
      0 on success, 1 on failure.
    """
    has_errors = False
    for fname, g in _games_for_filenames(filenames):
        if g is None:
            has_errors = True
            continue
        
        if overwrite and fname.endswith('.p8'):
            out_fname = fname
        else:
            if fname.endswith('.p8.png'):
                out_fname = fname[:-len('.p8.png')] + '_fmt.p8'
            else:
                out_fname = fname[:-len('.p8')] + '_fmt.p8'

        util.write('{} -> {}\n'.format(fname, out_fname))
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as outfh:
            procfunc(g, outfh, out_fname, args=args)
            
            outfh.seek(0)
            with open(out_fname, 'w', encoding='utf-8') as finalfh:
                finalfh.write(outfh.read())

    if has_errors:
        return 1
    return 0


def writep8(g, outfh, out_fname, args=None):
    """Writes the game to a .p8 file.

    If the original was a .p8.png file, this converts it to a .p8 file.

    If the original was a .p8 file, this just echos the game data into a new
    file. (This is mostly useful to validate the picotool library.)

    Args:
      g: The Game.
      outfh: The output filehandle.
      out_fname: The output filename, for error messages.
      args: The argparse parsed args object, or None.
    """
    g.to_p8_file(outfh, filename=out_fname)


def luamin(g, outfh, out_fname, args=None):
    """Reduces the Lua code for a cart to use a minimal number of characters.

    Args:
      g: The Game.
      outfh: The output filehandle.
      out_fname: The output filename, for error messages.
      args: The argparse parsed args object, or None.
    """
    g.to_p8_file(outfh, filename=out_fname,
                 lua_writer_cls=lua.LuaMinifyTokenWriter)
            

def luafmt(g, outfh, out_fname, args=None):
    """Rewrite the Lua code for a cart to use regular formatting.

    Args:
      g: The Game.
      outfh: The output filehandle.
      out_fname: The output filename, for error messages.
      args: The argparse parsed args object, or None.
    """
    g.to_p8_file(outfh, filename=out_fname,
                 lua_writer_cls=lua.LuaFormatterWriter,
                 lua_writer_args={'indentwidth': args.indentwidth})


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
    for fname, g in _games_for_filenames(args.filename):
        if len(args.filename) > 1:
            util.write('=== {} ===\n'.format(g.filename))
        _printast_node(g.lua.root)
    return 0


def luafind(args):
    """Looks for Lua code lines that match a pattern in one or more carts.

    Args:
      args: The argparser parsed args object.

    Returns:
      0 on success, 1 on failure.
    """
    # (The first argument is the pattern, but it's stored in args.filename.)
    filenames = list(args.filename)
    if len(filenames) < 2:
        util.error(
            'Usage: p8tool luafind <pattern> <filename> [<filename>...]\n')
        return 1
    pattern = re.compile(filenames.pop(0))

    # TODO: Tell the Lua class not to bother parsing, since we only need the
    # token stream to get the lines of code.
    for fname, g in _games_for_filenames(filenames):
        line_count = 0
        for l in g.lua.to_lines():
            line_count += 1
            if pattern.search(l) is None:
                continue
            if args.listfiles:
                util.write(fname + '\n')
                break
            try:
                util.write('{}:{}:{}'.format(fname, line_count, l))
            except UnicodeEncodeError as e:
                new_l = ''.join(c if ord(c) < 128 else '_' for c in l)
                util.write('{}:{}:{}'.format(fname, line_count, new_l))

    return 0


def main(orig_args):
    try:
        arg_parser = _get_argparser()
        args = arg_parser.parse_args(args=orig_args)
        if args.debug:
            util.set_verbosity(util.VERBOSITY_DEBUG)
        elif args.quiet:
            util.set_verbosity(util.VERBOSITY_QUIET)

        if args.command == 'stats':
            return stats(args)
        elif args.command == 'listlua':
            return listlua(args)
        elif args.command == 'listtokens':
            return listtokens(args)
        elif args.command == 'printast':
            return printast(args)
        elif args.command == 'writep8':
            return process_game_files(args.filename, writep8, args=args)
        elif args.command == 'luamin':
            return process_game_files(args.filename, luamin, args=args)
        elif args.command == 'luafmt':
            return process_game_files(args.filename, luafmt,
                                      overwrite=args.overwrite, args=args)
        elif args.command == 'luafind':
            return luafind(args)
    
        arg_parser.print_help()
        return 1

    except KeyboardInterrupt:
        util.error('\nInterrupted with Control-C, stopping.\n')
        return 1
