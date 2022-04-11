"""File formatter for .p8 files"""

__all__ = [
    'P8Formatter',
    'InvalidP8HeaderError',
    'InvalidP8VersionError',
    'InvalidP8SectionError',
    'P8IncludeNotFound',
    'P8IncludeOutsideOfAllowedDirectory',
    'InvalidP8Include'
]

import os.path
import re

from .p8png import P8PNGFormatter
from .base import BaseFormatter
from ..game import Game
from ... import util
from ...lua import lua
from ...gfx.gfx import Gfx
from ...gff.gff import Gff
from ...map.map import Map
from ...sfx.sfx import Sfx
from ...music.music import Music

HEADER_TITLE_STR = b'pico-8 cartridge // http://www.pico-8.com\n'
HEADER_VERSION_RE = re.compile(br'version (\d+)\r?\n')
SECTION_DELIM_RE = re.compile(br'__(\w+)__\r?\n')
INCLUDE_LINE_RE = re.compile(
    br'\s*#include\s+(\S+)(\.p8\.png|\.p8|\.lua)(\:\d+)?')
PICO8_CART_PATHS = [
    '~/AppData/Roaming/pico-8/carts',  # Windows
    '~/Library/Application Support/pico-8/carts',  # macOS
    '~/.lexaloffle/pico-8/carts',  # Linux
]
TAB_LINE_RE = re.compile(br'-->8')


class InvalidP8HeaderError(util.InvalidP8DataError):
    """Exception for invalid .p8 file header."""

    def __init__(self, bad_header, expected_header):
        self.bad_header = bad_header
        self.expected_header = expected_header

    def __str__(self):
        return 'Invalid .p8: missing or corrupt header. Found "%s" Expected "%s"' % (self.bad_header, self.expected_header)


class InvalidP8VersionError(util.InvalidP8DataError):
    """Exception for invalid .p8 version header."""

    def __init__(self, bad_version_line):
        self.bad_version_line = bad_version_line 

    def __str__(self):
        return ('Invalid .p8: invalid version header. found "%s"' % self.bad_version_line)


class InvalidP8SectionError(util.InvalidP8DataError):
    """Exception for invalid .p8 file section delimiter."""

    def __init__(self, bad_delim):
        self.bad_delim = bad_delim

    def __str__(self):
        return 'Invalid .p8: bad section delimiter {}'.format(
            repr(self.bad_delim))


class P8IncludeNotFound(util.InvalidP8DataError):
    pass


class P8IncludeOutsideOfAllowedDirectory(util.InvalidP8DataError):
    pass


class InvalidP8Include(util.InvalidP8DataError):
    pass


def _get_raw_data_from_p8_file(instr, filename=None):
    header_title_str = instr.readline()
    # use rstrip to normalize line endings
    if header_title_str.rstrip() != HEADER_TITLE_STR.rstrip():
        raise InvalidP8HeaderError(header_title_str, HEADER_TITLE_STR)
    header_version_str = instr.readline()
    version_m = HEADER_VERSION_RE.match(header_version_str)
    if version_m is None:
        raise InvalidP8VersionError(header_version_str)
    version = int(version_m.group(1))

    # (section is a text str.)
    section = None
    section_lines = {}
    while True:
        line = instr.readline()
        if not line:
            break
        section_delim_m = SECTION_DELIM_RE.match(line)
        if section_delim_m:
            section = str(section_delim_m.group(1), encoding='utf-8')
            section_lines[section] = []
        elif section:
            p8scii_line = lua.unicode_to_p8scii(
                str(line, encoding='utf-8'))
            section_lines[section].append(p8scii_line)

    class P8Data(object):
        pass
    data = P8Data()
    data.version = version
    data.section_lines = section_lines

    return data


def get_root_include_path(filename):
    """Determines the root path for the purposes of includes.

    PICO-8 restricts include paths to files in the PICO-8 cart root directory.
    If picotool detects that the input cart file is in such a path, it uses the
    cart root for includes. If the input cart is not in a recognized PICO-8
    cart path, includes are restricted to the directory containing the input
    file.

    Args:
        filename: The filename of the input cart.

    Returns:
        The include root path, or None if filename is None.
    """
    if filename is None:
        return None
    root_path = None
    full_file_path = os.path.abspath(
        os.path.normpath(
            os.path.expanduser(filename)))
    for candidate in PICO8_CART_PATHS:
        full_candidate_path = os.path.abspath(
            os.path.normpath(
                os.path.expanduser(candidate)))
        if full_file_path.startswith(full_candidate_path):
            root_path = full_candidate_path
    if root_path is None:
        root_path = os.path.dirname(full_file_path)
    return root_path


def lines_for_tab(lines_iter, inc_tab):
    """Yield just the lines for a given code tab.

    Args:
        lines_iter: An iterator of all code lines.
        inc_tab: The tab number, or None to yield all code lines.

    Yields:
        Each line of code for the requested tab, or for all tabs if inc_tab is
        None.
    """
    cur_tab = 0
    for line in lines_iter:
        if TAB_LINE_RE.match(line):
            cur_tab += 1
            if inc_tab is None:
                # Preserve tab cut lines if we're not actually selecting a tab.
                yield line
        elif inc_tab is None or inc_tab == cur_tab:
            yield line


def process_includes(lualines, filename=None):
    """Processes #include lines.

    Args:
        lualines: An iterable of lines of Lua code, as P8SCII bytestrings.
        filename: The filename of the input cart.

    Yields:
        Each line of Lua code, with #include lines processed.
    """
    root_path = get_root_include_path(filename)
    for line in lualines:
        m = INCLUDE_LINE_RE.match(line)
        if not m:
            yield line
            continue

        # (Only assert filename if there's an #include.)
        assert root_path is not None

        inc_path_b, inc_extension_b, inc_tab_b = m.groups()
        inc_path = str(inc_path_b, encoding='utf-8')
        inc_extension = str(inc_extension_b, encoding='utf-8')
        inc_tab = None
        if inc_tab_b:
            inc_tab_str = str(inc_tab_b, encoding='utf-8')
            inc_tab = int(inc_tab_str[1:])
        inc_full_path = os.path.abspath(
            os.path.normpath(
                os.path.join(
                    os.path.dirname(filename), inc_path + inc_extension)))
        if not inc_full_path.startswith(root_path):
            raise P8IncludeOutsideOfAllowedDirectory()
        if not os.path.isfile(inc_full_path):
            raise P8IncludeNotFound()

        if inc_extension == '.p8' or inc_extension == '.p8.png':
            p8_fmt_cls = (
                P8Formatter if inc_extension == '.p8'
                else P8PNGFormatter)
            with open(inc_full_path, 'rb') as fh:
                inc_game = p8_fmt_cls.from_file(
                    fh, filename=inc_full_path, do_includes=False)
                for line in lines_for_tab(inc_game.lua.to_lines(), inc_tab):
                    yield line
        else:
            with open(inc_full_path, 'rb') as fh:
                for line in fh:
                    yield line


class P8Formatter(BaseFormatter):
    @classmethod
    def from_file(
            cls, instr, filename=None, do_includes=True, *args, **kwargs):
        """Reads a game from a .p8.png file.

        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.
          do_includes: If True, process #include directives.

        Returns:
          A Game containing the game data.

        Raises:
          InvalidP8HeaderError
        """
        data = _get_raw_data_from_p8_file(instr, filename=filename)

        new_game = Game.make_empty_game(filename=filename)
        # Discard empty label until one is found in the file.
        new_game.label = None
        new_game.version = data.version
        for section in data.section_lines:
            if section == 'lua':
                lualines = data.section_lines[section]
                if do_includes:
                    lualines = process_includes(lualines, filename)
                new_game.lua = lua.Lua.from_lines(
                    lualines, version=data.version)
            elif section == 'gfx':
                new_game.gfx = Gfx.from_lines(
                    data.section_lines[section], version=data.version)
                my_map = getattr(new_game, 'map')
                if my_map is not None:
                    my_map._gfx = new_game.gfx
            elif section == 'gff':
                new_game.gff = Gff.from_lines(
                    data.section_lines[section], version=data.version)
            elif section == 'map':
                my_gfx = getattr(new_game, 'gfx')
                new_game.map = Map.from_lines(
                    data.section_lines[section],
                    version=data.version,
                    gfx=my_gfx)
            elif section == 'sfx':
                new_game.sfx = Sfx.from_lines(
                    data.section_lines[section], version=data.version)
            elif section == 'music':
                new_game.music = Music.from_lines(
                    data.section_lines[section], version=data.version)
            elif section == 'label':
                new_game.label = Gfx.from_lines(
                    data.section_lines[section], version=data.version)
            else:
                raise InvalidP8SectionError(section)

        return new_game

    @classmethod
    def to_file(
            cls, game, outstr, lua_writer_cls=None, lua_writer_args=None,
            filename=None, *args, **kwargs):
        """Writes a game to a file.

        Args:
          game: The Game to write.
          outstr: The output stream.
          lua_writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          lua_writer_args: Args to pass to the Lua writer.
          filename: The filename, if any, for tool messages.
        """
        outstr.write(HEADER_TITLE_STR)

        outstr.write(bytes('version %s\n' % game.version, 'utf-8'))

        # Sanity-check the Lua written by the writer.
        transformed_lua = lua.Lua.from_lines(
            game.lua.to_lines(writer_cls=lua_writer_cls,
                              writer_args=lua_writer_args),
            version=(game.version or 0))
        if transformed_lua.get_char_count() > lua.PICO8_LUA_CHAR_LIMIT:
            if filename is not None:
                util.error('{}: '.format(filename))
            util.error('warning: character count {} exceeds the PICO-8 '
                       'limit of {}\n'.format(
                           transformed_lua.get_char_count(),
                           lua.PICO8_LUA_CHAR_LIMIT))
        if transformed_lua.get_token_count() > lua.PICO8_LUA_TOKEN_LIMIT:
            if filename is not None:
                util.error('{}: '.format(filename))
            util.error('warning: token count {} exceeds the PICO-8 '
                       'limit of {}\n'.format(
                           transformed_lua.get_token_count(),
                           lua.PICO8_LUA_TOKEN_LIMIT))

        outstr.write(b'__lua__\n')
        ended_in_newline = None
        for line in game.lua.to_lines(
                writer_cls=lua_writer_cls,
                writer_args=lua_writer_args):
            outstr.write(bytes(lua.p8scii_to_unicode(line), 'utf-8'))
            ended_in_newline = line.endswith(b'\n')
        if not ended_in_newline:
            outstr.write(b'\n')

        outstr.write(b'__gfx__\n')
        for line in game.gfx.to_lines():
            outstr.write(line)

        if game.label:
            outstr.write(b'__label__\n')
            for line in game.label.to_lines():
                outstr.write(line)

        # PICO-8 emits an extra newline before __gff__ for no good reason, as
        # of 0.1.10c. PICO-8 doesn't care whether we do, but our tests want to
        # match the test cart data exactly.
        outstr.write(b'\n')
        outstr.write(b'__gff__\n')
        for line in game.gff.to_lines():
            outstr.write(line)

        outstr.write(b'__map__\n')
        for line in game.map.to_lines():
            outstr.write(line)

        outstr.write(b'__sfx__\n')
        for line in game.sfx.to_lines():
            outstr.write(line)

        outstr.write(b'__music__\n')
        for line in game.music.to_lines():
            outstr.write(line)

        outstr.write(b'\n')
