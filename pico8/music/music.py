""""""

__all__ = ['Music']


class Music():
    """"""
    def __init__(self, version):
        """Initializer.

        If loading from a file, prefer Music.from_lines().

        Args:
          version: The Pico-8 data version from the game file header.
        """
        self._version = version
        pass

    @classmethod
    def from_lines(cls, lines, version):
        """
        Args:
          version: The Pico-8 data version from the game file header.
        """
        result = Music(version=version)
        return result
