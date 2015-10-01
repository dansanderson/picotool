""""""

__all__ = ['Sfx']


class Sfx():
    """"""
    def __init__(self, version):
        """Initializer.

        If loading from a file, prefer Sfx.from_lines().

        Args:
          version: The Pico-8 data version from the game file header.
        """
        self._version = version

    @classmethod
    def from_lines(cls, lines, version):
        """
        Args:
          version: The Pico-8 data version from the game file header.
        """
        result = Sfx(version=version)
        return result
