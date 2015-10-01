"""A container for a Pico-8 game, and routines to load and save game files."""


__all__ = [
    'Game',
    'InvalidP8HeaderError',
    'InvalidP8SectionError'
]


import re

from .. import util
from ..lua import Lua
from ..gfx import Gfx
from ..gff import Gff
from ..map import Map
from ..sfx import Sfx
from ..music import Music


HEADER_TITLE_STR = 'pico-8 cartridge // http://www.pico-8.com\n'
HEADER_VERSION_RE = re.compile('version (\d+)\n')
SECTION_DELIM_RE = re.compile('__(\w+)__\n')


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


class Game():
    """A Pico-8 game."""
    def __init__(self):
        """Initializer.

        Prefer factory functions such as Game.from_p8_file().
        """
        self.lua = None
        self.gfx = None
        self.gff = None
        self.map = None
        self.sfx = None
        self.music = None

    @classmethod
    def from_p8_file(cls, instr):
        """Loads a game from a .p8 file.
    
        Args:
          instr: The input stream.
    
        Returns:
          A Game containing the game data.
    
        Raises:
          InvalidP8Header
        """
        header_title_str = instr.readline()
        if header_title_str != HEADER_TITLE_STR:
            raise InvalidP8Header()
        header_version_str = instr.readline()
        version_m = HEADER_VERSION_RE.match(header_version_str)
        if version_m is None:
            raise InvalidP8Header()
        version = int(version_m.group(1))
    
        section = None
        section_lines = {}
        while True:
            line = instr.readline()
            if not line:
                break
            section_delim_m = SECTION_DELIM_RE.match(line)
            if section_delim_m:
                section = section_delim_m.group(1)
                section_lines[section] = []
            elif section:
                section_lines[section].append(line)
    
        new_game = cls()
        for section in section_lines:
            if section == 'lua':
                new_game.lua = Lua.from_lines(
                    section_lines[section], version=version)
            elif section == 'gfx':
                new_game.gfx = Gfx.from_lines(
                    section_lines[section], version=version)
            elif section == 'gff':
                new_game.gff = Gff.from_lines(
                    section_lines[section], version=version)
            elif section == 'map':
                new_game.map = Map.from_lines(
                    section_lines[section], version=version)
            elif section == 'sfx':
                new_game.sfx = Sfx.from_lines(
                    section_lines[section], version=version)
            elif section == 'music':
                new_game.music = Music.from_lines(
                    section_lines[section], version=version)
            else:
                raise InvalidP8Section(section)
    
        return new_game
