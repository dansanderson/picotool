"""File formatter for .rom files"""

__all__ = [
    'ROMFormatter',
]

from .base import BaseFormatter
# from .. import compress
# from ..game import Game
# from ... import util
# from ...lua.lua import Lua
# from ...gfx.gfx import Gfx
# from ...gff.gff import Gff
# from ...map.map import Map
# from ...sfx.sfx import Sfx
# from ...music.music import Music


# TODO: Refactor P8PNGFormatter to use this as a basis and separate out the
# PNG aspect. (It's the same data, P8PNG takes the extra step of merging with a
# label PNG file stegonographically.)


class ROMFormatter(BaseFormatter):
    @classmethod
    def from_file(cls, instr, filename=None, *args, **kwargs):
        """Reads a game from a .rom file.

        Args:
          instr: The input stream.
          filename: The filename, if any, for tool messages.

        Returns:
          A Game containing the game data.
        """
        raise NotImplementedError()

    @classmethod
    def to_file(
            cls, game, outstr, lua_writer_cls=None, lua_writer_args=None,
            filename=None, *args, **kwargs):
        """Writes a game to a .rom file.

        Args:
          game: The Game to write.
          outstr: The output stream.
          lua_writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          lua_writer_args: Args to pass to the Lua writer.
          filename: The filename, if any, for tool messages.
        """
        raise NotImplementedError()
