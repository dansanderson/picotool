"""The main routines for the command-line tool."""

__all__ = ['main']


import argparse

from . import util


def _get_argparser():
    """Builds and returns the argument parser."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''
        '''))
    parser.add_argument(
        'command', type=str, nargs='1',
        help='the command to execute')
    parser.add_argument(
        'filename', type=str, nargs='*',
        help='the names of files to process')
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
        '-q', '--quiet', action='store_true',
        help='suppresses inessential messages')

    return parser


def main(orig_args):
    args = _get_argparser().parse_args(args=orig_args)
    util.set_quiet(args.quiet)

    has_errors = False

    # TODO: ...

    return 0
