# picotool: Tools and Python libraries for manipulating Pico-8 game files

[Pico-8](http://www.lexaloffle.com/pico-8.php) is a *fantasy game console* by [Lexaloffle Games](http://www.lexaloffle.com/). The Pico-8 runtime environment runs *cartridges* (or *carts*): game files containing code, graphics, sound, and music data. The console includes a built-in cartridge editor for writing games. Game cartridge files can also be played in a browser, and can be posted to the Lexaloffle bulletin board or exported to any website.

There are two major cartridge data formats supported by Pico-8: a text-based format (`.p8`), and a PNG-based binary format (`.p8.png`). The PNG file can be viewed as an image that serves as a cover image for the cartridge; the actual game data is encoded in the image data.

The `picotool` suite of tools and libraries can read `.p8` and `.p8.png` files, and can write `.p8` files. The suite is implemented entirely in [Python 3](https://www.python.org/). The tools can examine and transform cartridges in various ways, and you can implement your own tools to access and modify cartridge data with the Python libraries.

**Note:** `picotool` is in its early days! See "Known issues" below.


## Installing picotool

To install the `picotool` tools and libraries:

1. Download and unpack [the zip archive](https://github.com/dansanderson/picotool/archive/master.zip), or use Git to clone [the Github repository](https://github.com/dansanderson/picotool).
   * Unpacking the zip archive creates a root directory named `picotool-master`. When cloning the repo, this is just `picotool`, or whatever you named it when you cloned it.
1. Install [Python 3](https://www.python.org/), if necessary. (picotool has not been tested with Python 2.)
1. To enable PNG support, install the [PyPNG library](https://github.com/drj11/pypng):
   ```
   python3 -m pip install pypng
   ```

## Using picotool

To use a tool, you run the `p8tool` command with the appropriate arguments. Without arguments, it prints a help message. The first argument is the name of the tool to run (such as `stats`), followed by the arguments expected by that tool.

For example, to print statistics about a cart named `helloworld.p8.png`:

```
./picotool-master/p8tool stats helloworld.p8.png
```


### p8tool stats

The `stats` tool prints statistics about one or more carts. Given one or more cart filenames, it analyzes each cart, then prints information about it.

```
% ./picotool-master/p8tool stats ./picotool-master/tests/testdata/helloworld.p8.png 
hello world (helloworld.p8.png)
by zep
version: 0  lines: 48  chars: 419  tokens: 134
```

This command accepts an optional `--csv` argument. If provided, the command prints the statistics in a CSV format suitable for importing into a spreadsheet. This is useful when tallying statistics about multiple carts for comparative analysis.

```
% ./picotool-master/p8tool --csv stats mycarts/*.p8* >cartstats.csv
```


### p8tool listlua

The `listlua` tool extracts the Lua code from a cart, then prints it exactly as it appears in the cart.

```
% ./picotool-master/p8tool stats ./picotool-master/tests/testdata/helloworld.p8.png 
-- hello world
-- by zep

t = 0

music(0)

function _update()
 t += 1
end

function _draw()
 cls()

...
```


### p8tool listtokens

The `listtokens` tool is similar to `listlua`, but it identifies which characters picotool recognizes as a single token.

```
% ./picotool-master/p8tool stats ./picotool-master/tests/testdata/helloworld.p8.png 
<-- hello world>
<-- by zep>

<0:t>< ><1:=>< ><2:0>

<3:music><4:(><5:0><6:)>

<7:function>< ><8:_update><9:(><10:)>
< ><11:t>< ><12:+=>< ><13:1>
<14:end>

<15:function>< ><16:_draw><17:(><18:)>
< ><19:cls><20:(><21:)>

...
```

When picotool parses Lua code, it separates out comments, newlines, and spaces, as well as proper Lua tokens. The Lua tokens appear with an ascending number, illustrating how picotool counts the tokens. Non-token elements appear with similar angle brackets but no number. Newlines are rendered as is, without brackets, to make them easy to read.

**Note:** picotool does not currently count tokens the same way Pico-8 does. One purpose of this tool is to help troubleshoot and fix this discrepancy. See "Known issues."


## Building new tools

picotool provides a general purpose library for accessing and manipulating Pico-8 cart data. You can add the `picotool` directory to your `PYTHONPATH` environment variable (or append `sys.path` in code), or just copy the `pico8` module to the directory that contains your code.

The easiest way to load a cart from a file is with the `Game.from_filename()` method, in the `pico8.game.game` module:

```python
#!/usr/bin/env python3

from pico8.game import game

g = game.Game.from_filename('mycart.p8.png')
print('Tokens: {}'.format(g.lua.get_token_count()))
```

Aspects of the game are accessible as attributes of the `Game` object:

* `lua`
* `gfx`
* `gff`
* `map`
* `sfx`
* `music`


## Developing picotool

If you want to change the picotool code and run its test suite, you will need the [Nose test runner](https://nose.readthedocs.org/en/latest/) and the [coverage tool](https://pypi.python.org/pypi/coverage). You can install these with `pip`:

```
python3 -m pip install nose coverage
```

To run the test suite:

```
python3 run_tests.py
```

By default, this produces an HTML coverage report in the `cover` subdirectory. Open `.../picotool-master/cover/index.html` in a browser to see it.


## Known issues

* picotool and Pico-8 count tokens and characters in slightly different ways, resulting in different counts. More refinement is needed so that picotool matches Pico-8. The largest cart posted to the BBS has 31,850 chars and 8,141 tokens according to Pico-8, and 31,656 chars (-196) and 8,284 tokens (+143) according to picotool.

* Pico-8's special single-line short form of the Lua `if` statement has some undocumented behavior that is currently not supported by picotool. Of all of the carts analyzed so far, only one such behavior is used but not yet supported: if the statement after the condition is a `do ... end` block, then the block is allowed to use multiple lines. `if (cond) do ... end` can always be rewritten as `if cond then ... end`.


## Future plans

picotool began as a simple project to build a code formatter/minifier for Pico-8, and eventually became a general purpose library for manipulating Pico-8 cart data. The goal is to make it easy to build new tools and experiments for analyzing and transforming carts, as well as to make new and interesting tools for Pico-8 developers.

TODO:

* Arg ordering bug for `p8tool --csv stats ...`
* Game save API
* Semantic APIs for the non-Lua sections
* Rewrite expression AST to represent operator precedence
* Add module loading shortcuts (to avoid module paths like `pico8.game.game.Game`)
* More Pico-8-like char counting
* More Pico-8-like token counting
* Improved reporting of parser errors
* Tool: stats with info about other regions, e.g. color histograms
* Tool: AST visualizer
* Tool: Lua minifier
* Tool: Lua pretty printer
* Tool: Lua "linker" (import stitching)
* Tool: Game launcher menu
