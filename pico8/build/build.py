import os

from .. import util
from ..game import game
from ..lua import lua


def do_build(args):
    """Executor for the p8tool build command.

    Args:
        args: The argparse.Namespace arguments object.
    """
    if (not args.filename.endswith('.p8') and
            not args.filename.endswith('.p8.png')):
        util.error('Output filename must end with .p8 or .p8.png.')
        return 1

    empty_source = game.Game.make_empty_game(filename=args.filename)

    # Determine whether output file exists and if so load it, otherwise
    # create an empty cart.
    if os.path.exists(args.filename):
        result = game.Game.from_filename(args.filename)
    else:
        result = game.Game.make_empty_game(filename=args.filename)

    for section in ('lua', 'gfx', 'gff', 'map', 'sfx', 'music'):
        if getattr(args, section, None) is not None:

            # Verify "empty" overrides don't conflict with provided sources.
            if getattr(args, 'empty_' + section, False):
                util.error('Cannot specify --%s and --empty-%s args '
                           'together.' % (section, section))
                return 1

            # Verify source files exist and are of supported types.
            fn = getattr(args, section)
            if not os.path.exists(fn):
                util.error('File "%s" given for --%s arg does not exist.' %
                           (fn, section))
                return 1
            # TODO: support .png files as gfx source
            if (not fn.endswith('.p8') and
                    not fn.endswith('.p8.png') and
                    not (section == 'lua' and fn.endswith('.lua'))):
                util.error(
                    'Unsupported file type for --%s arg.' % (section,))
                return 1

            # Load section from source and store it in the result.
            # TODO: support .png files as gfx source
            if section == 'lua' and fn.endswith('.lua'):
                with open(fn) as infh:
                    # TODO: support require() with .lua
                    result.lua = lua.Lua.from_lines(
                        infh, version=game.DEFAULT_VERSION)
            else:
                source = game.Game.from_filename(fn)
                setattr(result, section, getattr(source, section))

        elif getattr(args, 'empty_' + section, False):
            setattr(result, section, getattr(empty_source, section))

    # Save result as args.filename.
    # TODO: allow overriding the label source for .p8.png
    result.to_file(filename=args.filename)

    return 0
