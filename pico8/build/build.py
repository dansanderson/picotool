import os

from .. import util
from ..game import file
from ..game import game
from ..lua import lua
from ..lua import parser
from ..lua import lexer


# The default Lua load path if neither PICO8_LUA_PATH nor --lua-path are set.
DEFAULT_LUA_PATH = '?;?.lua'

# Names of the PICO-8 game loop functions stripped from require()'d files
# (unless told not to).
GAME_LOOP_FUNCTION_NAMES = (b'_init', b'_update', b'_update60', b'_draw')

# Lua code added to the beginning of a cart that uses require().
# 1: the package table with loaded and _c tables
REQUIRE_LUA_PREAMBLE_PACKAGE = (b'package={loaded={},_c={}}\n',)

# 2: the require() function
REQUIRE_LUA_PREAMBLE_REQUIRE = (
    b'function require(p)\n',
    b'local l=package.loaded\n',
    b'if (l[p]==nil) l[p]=package._c[p]()\n',
    b'if (l[p]==nil) l[p]=true\n',
    b'return l[p]\n',
    b'end\n')


class LuaBuildError(parser.ParserError):
    """User error specific to Lua building."""
    pass


def _locate_require_file(p, file_path, lua_path=None):
    """Get the full file path for a require().

    Args:
        p: The require() path.
        file_path: The path of the file containing the require().
        lua_path: The library loading path, in PICO8_LUA_PATH format.

    Returns:
        The absolute path to the require()'d file, or None if no file
        was found for the given arguments.
    """
    rel_path_base = os.path.dirname(file_path)
    if lua_path is None:
        lua_path = os.getenv('PICO8_LUA_PATH')
        if lua_path is None:
            lua_path = DEFAULT_LUA_PATH
    for lookup_p in lua_path.split(';'):
        candidate = lookup_p.replace('?', p)
        if not candidate.startswith(os.path.sep):
            candidate = os.path.join(rel_path_base, candidate)
        if os.path.isfile(candidate):
            return candidate
    return None


class RequireWalker(lua.BaseASTWalker):
    def _error_at_node(self, msg, node):
        raise LuaBuildError(msg, self._tokens[node.start_pos])

    def _walk_FunctionCall(self, node):
        """Walk a function call node.

        Args:
            node: A parser.FunctionCall node that may or may not be a require()
                call

        Yields:
            A tuple (require_path, use_game_loop, require_token).

            require_path: the string value passed to require()
            use_game_loop: the boolean option passed to require()'s options
                table
            require_token: the lexer.Token for the require() statement, for
                error messages
        """
        if (isinstance(node.exp_prefix, parser.VarName) and
                node.exp_prefix.name == lexer.TokName(b'require')):
            arg_exps = node.args.explist.exps if node.args.explist else []
            if len(arg_exps) < 1 or len(arg_exps) > 2:
                self._error_at_node('require() has {} args, should have 1 or 2'
                                    .format(len(arg_exps)), node)
            if (not isinstance(arg_exps[0], parser.ExpValue) or
                    not isinstance(arg_exps[0].value, lexer.TokString)):
                self._error_at_node('require() first argument must be a '
                                    f'string literal, but first argument is {arg_exps[0]}', node)
            require_path = arg_exps[0].value.value

            use_game_loop = False
            if len(arg_exps) == 2:
                if (not isinstance(arg_exps[1], parser.ExpValue) or
                        not isinstance(arg_exps[1].value, parser.TableConstructor)):  # noqa: E501
                    self._error_at_node('require() second argument must be a '
                                        'table literal', node)
                # require() only has one valid option for now, so hard-code
                # this expectation
                if (len(arg_exps[1].value.fields) != 1 or
                    arg_exps[1].value.fields[0].key_name != lexer.TokName(b'use_game_loop') or  # noqa: E501
                        type(arg_exps[1].value.fields[0].exp.value) != bool):
                    self._error_at_node(
                        'Invalid require() options; did '
                        'you mean {use_game_loop=true} ?', node)
                use_game_loop = arg_exps[1].value.fields[0].exp.value

            yield (require_path, use_game_loop, self._tokens[node.start_pos])


def _evaluate_require(ast, file_path, package_lua, lua_path=None):
    """Evaluate require() statements in a Lua AST.

    See the picotool README.md for a complete description of the intended
    behavior of require().

    This function is called recursively on require()'d files.

    Args:
        ast: A lua.Lua object.
        file_path: A path to the file containing the Lua code for the AST.
        package_lua: The master dict of require() strings to Lua ASTs.
        lua_path: The Lua load path. If None, uses: ?;?.lua;?.p8;?.p8.png

    Raises:
        FileNotFoundError.
    """
    walker = RequireWalker(ast.tokens, ast.root)
    for (require_path, use_game_loop, require_token) in walker.walk():
        require_path_str = require_path.decode(encoding='utf-8')

        # Disallow chars that select files outside of the load path.
        if b'./' in require_path or require_path.startswith(b'/'):
            raise LuaBuildError(
                'require() filename cannot contain "./" or "../" or start '
                'with "/"', require_token)

        if require_path not in package_lua:
            reqd_filepath = _locate_require_file(
                require_path_str, file_path, lua_path=lua_path)
            if reqd_filepath is None:
                raise LuaBuildError(
                    'require() file {} not found; used load path {}'.format(require_path_str, lua_path),  # noqa: E501
                    require_token)

            # TODO: support loading required code from .p8 and .p8.png files.
            with open(reqd_filepath, 'rb') as infh:
                reqd_lua = lua.Lua.from_lines(
                    infh, version=game.DEFAULT_VERSION)

            # TODO: Technically the use_game_loop option needs to be part of
            # the package key because it results in a different package than
            # that without the option. As is, the first require() the parser
            # encounters determines the option. (This is not necessarily the
            # first require() the Lua interpreter encounters.)

            if not use_game_loop:
                reqd_lua.root.stats[:] = [
                    s for s in reqd_lua.root.stats
                    if not isinstance(s, parser.StatFunction) or
                    s.funcname.namepath[0].value not in GAME_LOOP_FUNCTION_NAMES]  # noqa: E501
                reqd_lua.reparse(writer_cls=lua.LuaASTEchoWriter)

            package_lua[require_path] = reqd_lua
            _evaluate_require(reqd_lua, reqd_filepath,
                              package_lua, lua_path=lua_path)


def _prepend_package_lua(orig_ast, package_lua):
    """Prepend all the require() material to an AST.

    Args:
        orig_ast: The lua.Lua object for the original code.
        package_lua: A mapping of require() strings to lua.Lua objects.

    Returns:
        The new lua.Lua object with the package code and preamble prepended.
        If package_lua is empty, returns orig_ast.
    """
    if not package_lua:
        return orig_ast

    package_header = []
    package_header.extend(REQUIRE_LUA_PREAMBLE_PACKAGE)
    for pth, ast in package_lua.items():
        escaped_pth = pth.replace(b'"', b'\\"')
        package_header.append(
            b'package._c["' + escaped_pth + b'"]=function()\n')
        package_header.extend(ast.to_lines())
        package_header.append(b'end\n')
    package_header.extend(REQUIRE_LUA_PREAMBLE_REQUIRE)
    new_code = package_header + list(orig_ast.to_lines())

    return lua.Lua.from_lines(new_code, version=game.DEFAULT_VERSION)


def _remove_global_return(ast):
    """Remove return statements from the root level of an AST.

    PICO-8 never allows a return statement at the root level of cart code. To
    support a library development workflow where the library code contains a
    game loop that tests the library as well as a Lua module return statement,
    return statements are removed silently from the root of a built cart's
    main code. (They are not removed from require()'d carts.)

    This removal occurs in place on the given AST object.

    Args:
        ast: The lua.Lua object.
    """
    # ast.root.stats[:] = [
    #    s for s in ast.root.stats
    #    if not isinstance(s, parser.StatReturn)]
    # ast.reparse(writer_cls=lua.LuaASTEchoWriter)
    pass


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
        result = file.from_file(args.filename)
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
            if (not fn.endswith('.p8') and
                    not fn.endswith('.p8.png') and
                    not (section == 'lua' and fn.endswith('.lua'))):
                util.error(
                    'Unsupported file type for --%s arg.' % (section,))
                return 1

            # Load section from source and store it in the result.
            if section == 'lua' and fn.endswith('.lua'):
                with open(fn, 'rb') as infh:
                    result.lua = lua.Lua.from_lines(
                        infh, version=game.DEFAULT_VERSION)
                    package_lua = {}

                    # ADDED: try-except
                    try:
                        _evaluate_require(
                            result.lua, file_path=fn, package_lua=package_lua,
                            lua_path=getattr(args, 'lua_path', None))
                    except LuaBuildError as e:
                        print(f"LuaBuildError caught on _evaluate_require with top file: {fn}")
                        print("The error may be located in any file recursively required, comment out until you find the culprit.")
                        print(f"msg: {e.msg}")
                        print(f"token: {e.token}")
                        print("Passing error upward")
                        raise

                    if getattr(args, 'optimize_tokens', False):
                        # TODO: perform const subst, dead code elim, taking
                        # package_lua into account
                        raise NotImplementedError(
                            '--optimize_tokens not yet implemented, sorry')

                    result.lua = _prepend_package_lua(result.lua, package_lua)
                    _remove_global_return(result.lua)
            else:
                source = file.from_file(fn)
                setattr(result, section, getattr(source, section))

        elif getattr(args, 'empty_' + section, False):
            setattr(result, section, getattr(empty_source, section))

    # TODO: allow overriding the label source for .p8.png

    # Save result as args.filename.
    lua_writer_cls = None
    lua_writer_args = None
    if getattr(args, 'lua_format', False):
        lua_writer_cls = lua.LuaFormatterWriter,
        lua_writer_args = {
            'indentwidth': args.indentwidth,
            # 'keep_property_names': args.keep_property_names,
            'keep_all_names': args.keep_all_names,
            'keep_names_from_file': args.keep_names_from_file}
    elif getattr(args, 'lua_minify', False):
        lua_writer_cls = lua.LuaMinifyTokenWriter
    file.to_file(
        result, filename=args.filename,
        lua_writer_cls=lua_writer_cls,
        lua_writer_args=lua_writer_args)

    return 0
