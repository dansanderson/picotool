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
        'filename', type=str, nargs='*',
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
            yield None
        except parser.ParserError as e:
            util.error('{}: {}\n'.format(fname, e))
            if print_tracebacks:
                import traceback
                traceback.print_exc(file=util._error_stream)
            yield None
        except Exception as e:
            util.error('{}: {}\n'.format(fname, e))
            if print_tracebacks:
                import traceback
                traceback.print_exc(file=util._error_stream)
            yield None
        else:
            yield g

        
def main(orig_args):
    arg_parser = _get_argparser()
    args = arg_parser.parse_args(args=orig_args)
    util.set_quiet(args.quiet)

    has_errors = False

    if args.command == 'stats':
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
                'Line Count'
            ])

        for g in _games_for_filenames(args.filename,
                                      print_tracebacks=args.debug):
            if args.csv:
                csv_writer.writerow([
                    os.path.basename(fname),
                    g.lua.get_title(),
                    g.lua.get_byline(),
                    g.lua.version,
                    g.lua.get_char_count(),
                    g.lua.get_token_count(),
                    g.lua.get_line_count()
                ])
            else:
                title = g.lua.get_title()
                byline = g.lua.get_byline()
                    
                if title is not None:
                    print('{} ({})'.format(title, os.path.basename(g.filename)))
                else:
                    print(os.path.basename(g.filename))
                if byline is not None:
                    print(byline)
                print('version: {}  lines: {}  chars: {}  tokens: {}'.format(
                    g.lua.version, g.lua.get_line_count(),
                    g.lua.get_char_count(), g.lua.get_token_count()))
                print('')

    elif args.command == 'listlua':
        for g in _games_for_filenames(args.filename,
                                      print_tracebacks=args.debug):
            if len(args.filename) > 1:
                util.write('=== {} ===\n'.format(g.filename))
            for l in g.lua.to_lines():
                util.write(l)
            util.write('\n')

    elif args.command == 'listtokens':
        for g in _games_for_filenames(args.filename,
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

    else:
        arg_parser.print_help()
        return 1

    return 0
