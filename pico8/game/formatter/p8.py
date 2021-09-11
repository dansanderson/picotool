"""File formatter for .p8 files"""

__all__ = [
    'P8Formatter',
    'InvalidP8HeaderError',
    'InvalidP8SectionError',
]

import re

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
HEADER_VERSION_RE = re.compile(br'version (\d+)\n')
SECTION_DELIM_RE = re.compile(br'__(\w+)__\n')


class InvalidP8HeaderError(util.InvalidP8DataError):
    """Exception for invalid .p8 file header."""

    def __str__(self):
        return 'Invalid .p8: missing or corrupt header'


class InvalidP8SectionError(util.InvalidP8DataError):
    """Exception for invalid .p8 file section delimiter."""

    def __init__(self, bad_delim):
        self.bad_delim = bad_delim

    def __str__(self):
        return 'Invalid .p8: bad section delimiter {}'.format(
            repr(self.bad_delim))


def _get_raw_data_from_p8_file(instr, filename=None):
    header_title_str = instr.readline()
    if header_title_str != HEADER_TITLE_STR:
        raise InvalidP8HeaderError()
    header_version_str = instr.readline()
    version_m = HEADER_VERSION_RE.match(header_version_str)
    if version_m is None:
        raise InvalidP8HeaderError()
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


class P8Formatter(BaseFormatter):
    @classmethod
    def from_file(cls, instr, filename=None, *args, **kwargs):
        """Reads a game from a .p8.png file.

        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.

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
                new_game.lua = lua.Lua.from_lines(
                    data.section_lines[section], version=data.version)
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
