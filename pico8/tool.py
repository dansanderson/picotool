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
        'filename', type=str, nargs='*',
        help='the names of files to process')

    return parser


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
            
        for fname in args.filename:
            if not fname.endswith('.p8.png') and not fname.endswith('.p8'):
                print('{}: filename must end in .p8 or .p8.png'.format(fname))
                continue
            is_p8 = fname.endswith('.p8')

            g = None
            try:
                if is_p8:
                    with open(fname, 'r') as fh:
                        g = game.Game.from_p8_file(fh)
                else:
                    with open(fname, 'rb') as fh:
                        g = game.Game.from_p8png_file(fh)
            except lexer.LexerError as e:
                print('{}: {}'.format(fname, e))
                return 1
            except parser.ParserError as e:
                print('{}: {}'.format(fname, e))
                import traceback
                traceback.print_exc()
                return 1
            except Exception as e:
                print('{}: {}'.format(fname, e))
                import traceback
                traceback.print_exc()
                return 1
            
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
                    print('{} ({})'.format(title, os.path.basename(fname)))
                else:
                    print(os.path.basename(fname))
                if byline is not None:
                    print(byline)
                print('version: {}  lines: {}  chars: {}  tokens: {}'.format(
                    g.lua.version, g.lua.get_line_count(),
                    g.lua.get_char_count(), g.lua.get_token_count()))
                print('')
    else:
        arg_parser.print_help()
        return 1

    return 0
