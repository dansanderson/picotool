"""Base class for file formatters"""

__all__ = [
    'BaseFormatter',
]


class BaseFormatter:
    @classmethod
    def from_file(cls, instr, filename=None, *args, **kwargs):
        """Reads a game from a file.

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
        """Writes a game to a file.

        Args:
          game: The Game to write.
          outstr: The output stream.
          lua_writer_cls: The Lua writer class to use. If None, defaults to
            LuaEchoWriter.
          lua_writer_args: Args to pass to the Lua writer.
          filename: The filename, if any, for tool messages.
        """
        raise NotImplementedError()
