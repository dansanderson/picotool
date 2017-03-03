># picotool: Tools and Python libraries for manipulating Pico-8 game files

[Pico-8](http://www.lexaloffle.com/pico-8.php) is a *fantasy game console* by [Lexaloffle Games](http://www.lexaloffle.com/). The Pico-8 runtime environment runs *cartridges* (or *carts*): game files containing code, graphics, sound, and music data. The console includes a built-in editor for writing games. Game cartridge files can be played in a browser, and can be posted to the Lexaloffle bulletin board or exported to any website.

`picotool` is a suite of tools and libraries for building and manipulating Pico-8 game cartridge files. The suite is implemented in, and requires, [Python 3](https://www.python.org/). The tools can examine and transform cartridges in various ways, and you can implement your own tools to access and modify cartridge data with the Python libraries.

Useful tools include:

* `p8tool build`: assembles cartridges from multiple sources, as part of a game development workflow
* `p8tool stats`: reports statistics on one or many cartridge files
* `p8tool listlua`: prints the Lua code of a cartridge
* `p8tool luafind`: searches the Lua code of a collection of cartridges
* `p8tool luafmt`: formats the Lua code of a cartridge to make it easier to read

There are additional tools that are mostly useful for demonstrating and troubleshooting the library: `writep8`, `listtokens`, `printast`, `luamin`. A separate demo, `p8upsidedown`, uses picotool to transform the code and data of a game to turn it upsidedown.

`picotool` supports reading and writing both of Pico-8's cartridge file formats: the text-based format `.p8`, and the PNG-based binary format `.p8.png`.


## Installing picotool

To install the `picotool` tools and libraries:

1. Download and unpack [the zip archive](https://github.com/dansanderson/picotool/archive/master.zip), or use Git to clone [the Github repository](https://github.com/dansanderson/picotool).
   * Unpacking the zip archive creates a root directory named `picotool-master`. When cloning the repo, this is just `picotool`, or whatever you named it when you cloned it.
1. Install [Python 3](https://www.python.org/) version 3.4 or later, if necessary. (picotool has not been tested with Python 2.)
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


### p8tool build

The `build` tool creates or updates a cartridge file using other files as sources. It is intended as a part of a game development workflow, producing the final output cartridge.

The tool takes the filename of the output cartridge, with additional arguments describing the build. If the output cartridge does not exist, the build starts with an empty cartridge. Otherwise, it uses the existing cartridge as the default, and overwrites sections of it based on the arguments.

For example, you can create a cartridge in Pico-8, use Pico-8's built-in graphics and sound editors, then use `p8tool build` to replace the Lua code with the contents of a `.lua` file:

```
% ./picotool-master/p8tool build mygame.p8.png --lua mygame.lua
```

As another example, to create a new cartridge using the spritesheet (`gfx`) from one cartridge file, music (`sfx`, `music`) from another, and Lua code from a `.lua` file:

```
% ./picotool-master/p8tool build mygame.p8.png --gfx mygamegfx.p8 --sfx radsnds.p8.png --music radsnds.p8.png --lua mygame.lua
```

You can also erase a section of an existing cart with an argument such as `--empty-map`. 
 
The available arguments are as follows:

* `--lua LUA`: use Lua code from the given cart or `.lua` file
* `--gfx GFX`: use spritesheet from the given cart
* `--gff GFF`: use sprite flags from the given cart
* `--map MAP`: use map from the given cart
* `--sfx SFX`: use sound effects from the given cart
* `--music MUSIC`: use music patterns from the given cart
* `--empty-lua`: use an empty Lua code section
* `--empty-gfx`: use an empty spritesheet
* `--empty-gff`: use empty sprite flags
* `--empty-map`: use an empty map
* `--empty-sfx`: use empty sound effects
* `--empty-music`: use empty music patterns

If the output cart filename ends with `.p8.png`, the result a cartridge with a label image. If the file already exists, the cartridge label is reused. If the file does not exist, an empty cartridge label is used. To use a non-empty label, you must open the cart in Pico-8, take a screenshot (press F6 while running), set the title and byline in the first two lines of code (as Lua comments), then save the `.p8.png` file from Pico-8. Future runs of `p8tool build` will reuse the label.

#### Packages and the require() function

p8tool build supports a special feature for organizing your Lua code, called packages. When loading Lua code from a file with the `--lua mygame.lua` argument, your program can call a function named `require()` to load Lua code from another file. This is similar to the `require()` function available in some other Lua environments, with some subtle differences due to how picotool does this at build time instead of at run time.

Consider the following simple example. Say you have a function you like to use in several games in a file called `mylib.lua`:

```
function handyfunc(x, y)
  return x + y
end

handynumber = 3.14
```

Your main game code is in a file named `mygame.lua`. To use the `handyfunc()` function within `mygame.lua`, call `require()` to load it:

```
require("mylib")

result = handyfunc(2, 3)
print(result)

r = 5
area = handynumber * r * r
```

All globals defined in the required file are set as globals in your program when `require()` is called. While this is easy enough to understand, this has the disadvantage of polluting the main program's global namespace.

A more typical way to write a Lua package is to put everything intended to be used by other programs in a table:

```
HandyPackage = {
  handyfunc = function(x, y)
    return x + y
  end,
  handynumber = 3.14,
}
```

Then in `mygame.lua`:

``` 
require("mylib")

result = HandyPackage.handyfunc(2, 3)
```

This is cleaner, but still has the disadvantage that the package must be known by the global name `HandyPackage` wihtin `mygame.lua`. To fix this, Lua packages can return a value with the `return` statement. This becomes the return value for the `require()` call. Furthermore, Lua packages can declare `local` variables that are not accessible to the main program. You can use these features to hide explicit names and return the table for the package:

```
local HandyPackage = {
  handyfunc = function(x, y)
    return x + y
  end,
  handynumber = 3.14,
}

return HandyPackage
```

The main program uses the return value of `require()` to access the package:
 
```
HandyPackage = require("mylib")

result = HandyPackage.handyfunc(2, 3)
```

The `require()` function only evaluates the package's code once. Subsequent calls to `require()` with the same string name do not reevaluate the code. They just return the package's return value. Packages can safely require other packages, and only the first encountered `require()` call evaluates the package's code.

#### Where packages are located

The first argument to `require()` is a string name. picotool finds the file that goes with the string name using a library lookup path. This is a semicolon-delimited (`;`) list of filesystem path patterns, where each pattern uses a question mark (`?`) where the string name would go.

The default lookup path is `?;?.lua`. With this path, `require("mylib")` would check for a file named `mylib`, then for a file named `mylib.lua`, each in the same directory as the file containing the `require()` call. The lookup path can also use absolute filesystem paths (such as `/usr/share/pico8/lib/?.lua`). You can customize the lookup path either by passing the `--lua-path=...` argument on the command line, or by setting the PICO8_LUA_PATH environment variable.

For example, with this environment variable set:

```
PICO8_LUA_PATH=?;?.lua;/home/dan/p8libs/?/?.p8
```

The require("3dlib") statement would look for these files, in this order, with paths relative to the file containing the require() statement:

```
3dlib
3dlib.lua
/home/dan/p8libs/3dlib/3dlib.p8
```

To prevent malicious code from accessing arbitrary files on your hard drive (unlikely but it's nice to prevent it), the `require()` string cannot refer to files in parent directories with `../`. It can refer to child directories, such as `require("math/linear")`.

As with Lua, packages are remembered by the string name used with `require()`. This means it is possible to have two copies of the same package, each known by a different name, if it can be reached two ways with the lookup path. For example, if the file is named `foo.lua` and the lookup path is `?;?.lua`, `require("foo")` and `require("foo.lua")` treat the same file as two different packages.

#### Packages and game loop functions

When you write a library of routines for Pico-8, you probably want to write test code for those routines. picotool assumes that this test code would be executed in a Pico-8 game loop, such that the library can be in its own test cart. For this purpose, you can write your library file with `_init()`, `_update()` or `_update60()`, and `_draw()` functions that test the library. By default, `require()` will strip the game loop functions from the library when including it in your game code so they don't cause conflicts or consume tokens.

For example:

```
local HandyPackage = {
  handyfunc = function(x, y)
    return x + y
  end,
  handynumber = 3.14,
}

function _update()
  test1 = HandyPackage.handyfunc(2, 3)
end
function _draw()
  cls()
  print('test1 = '..test1)
end

return HandyPackage
```

If you want to keep the game loop functions present in a package, you can request them with a second argument to `require()`, like so:

``` 
require("mylib", {use_game_loop=true})
```

#### How require() actually works

Of course, Pico-8 does not actually load packages from disk when it runs the cartridge. Instead, picotool inserts each package into the cartridge code in a special way that replicates the behavior of the Lua `require()` feature.

When you run `p8tool build` with the `--lua=...` argument, picotool scans the code for calls to the `require()` function. If it sees any, it loads and parses the file associated with the string name, and does so again if the required file also has `require()` calls.

Each required library is stored once as a function object in a table inserted at the top of the final cartridge's code. A definition of the `require()` function is also inserted that finds and evaluates the package code in the table as needed.

To match Lua's behavior, `require()` maintains a table named `package.loaded` that maps string names to return values. As with Lua, you can reset this value to `nil` to force a `require()` to reevaluate a package.

This feature incurs a small amount of overhead in terms of tokens. Each library uses tokens for its own code, plus a few additional tokens for storing it in the table. The definition for `require()` is another 40 tokens or so. Naturally, the inserted code also consumes characters.

#### Formatting or minifying Lua in a built cart

You can tell `p8tool build` to format or minify the code in the built output using the `--lua-format` or `--lua-minify` command line arguments, respectively.

``` 
% ./picotool-master/p8tool build mycart.p8.png --lua=mygame.lua --lua-format
```

This is equivalent to building the cart then running `p8tool luafmt` or `p8tool luamin` on the result.


### p8tool stats

The `stats` tool prints statistics about one or more carts. Given one or more cart filenames, it analyzes each cart, then prints information about it.

```
% ./picotool-master/p8tool stats helloworld.p8.png 
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
% ./picotool-master/p8tool listlua helloworld.p8.png 
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


### p8tool luafmt

The `luafmt` tool rewrites the Lua region of a cart to make it easier to read, using regular indentation and spacing. This does not change the token count, but it may increase the character count, depending on the initial state of the code.

The command takes one or more cart filenames as arguments. For each cart with a name like `xxx.p8.png`, it writes a new cart with a name like `xxx_fmt.p8`.

```
% ./picotool-master/p8tool luafmt helloworld.p8.png 
% cat helloworld_fmt.p8
pico-8 cartridge // http://www.pico-8.com
version 5
__lua__
-- hello world
-- by zep

t = 0

music(0)

function _update()
  t += 1
end

function _draw()
  cls()

  for i=1,11 do
    for j0=0,7 do
      j = 7-j0
      col = 7+j
...
```

By default, the indentation width is 2 spaces. You can change the desired indentation width by specifying the `--indentwidth=...` argument:

```
% ./picotool-master/p8tool luafmt --indentwidth=4 helloworld.p8.png 
% cat helloworld_fmt.p8
...
function _update()
    t += 1
end

function _draw()
    cls()

    for i=1,11 do
        for j0=0,7 do
            j = 7-j0
            col = 7+j
...
```

The current version of `luafmt` is simple and mostly just adjusts indentation. It does not adjust spaces between tokens on a line, align elements to brackets, or wrap long lines.


### p8tool luafind

The `luafind` tool searches for a string or pattern in the code of one or more carts. The pattern can be a simple string or a regular expression that matches a single line of code.

Unlike common tools like `grep`, `luafind` can search code in .p8.png carts as well as .p8 carts. This tool is otherwise not particularly smart: it's slow (it runs every file through the parser), and doesn't support fancier `grep`-like features.

```
% ./picotool-master/p8tool luafind 'boards\[.*\]' *.p8*
test_gol.p8.png:11:  boards[1][y] = {}
test_gol.p8.png:12:  boards[2][y] = {}
test_gol.p8.png:14:    boards[1][y][x] = 0
test_gol.p8.png:15:    boards[2][y][x] = 0
test_gol.p8.png:20:boards[1][60][64] = 1
test_gol.p8.png:21:boards[1][60][65] = 1
test_gol.p8.png:22:boards[1][61][63] = 1
test_gol.p8.png:23:boards[1][61][64] = 1
test_gol.p8.png:24:boards[1][62][64] = 1
test_gol.p8.png:30:  return boards[bi][y][x]
test_gol.p8.png:36:      pset(x-1,y-1,boards[board_i][y][x] * alive_color)
test_gol.p8.png:54:          ((boards[board_i][y][x] == 1) and neighbors == 2)) then
test_gol.p8.png:55:        boards[other_i][y][x] = 1
test_gol.p8.png:57:        boards[other_i][y][x] = 0
```

You can tell `luafind` to just list the names of files containing the pattern without printing the lines using the `--listfiles` argument. Here's an example that looks for carts that contain examples of Lua OO programming:

```
% ./picotool-master/p8tool luafind --listfiles 'self,' *.p8*
11243.p8.png
12029.p8.png
12997.p8.png
13350.p8.png
13375.p8.png
13739.p8.png
15216.p8.png
...
```


### p8tool writep8

The `writep8` tool writes a game's data to a `.p8` file. This is mostly useful for converting a `.p8.png` file to a `.p8` file. If the input is a `.p8` already, then this just makes a copy of the file. (This can be used to validate that the picotool library can output its input.)

The command takes one or more cart filenames as arguments. For each cart with a name like `xxx.p8.png`, it writes a new cart with a name like `xxx_fmt.p8`.

```
% ./picotool-master/p8tool writep8 helloworld.p8.png 
% cat helloworld_fmt.p8
pico-8 cartridge // http://www.pico-8.com
version 5
__lua__
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


### p8tool luamin

The `luamin` tool rewrites the Lua region of a cart to use as few characters as possible. It does this by discarding comments and extraneous space characters, and renaming variables and functions. This does not change the token count.

The command takes one or more cart filenames as arguments. For each cart with a name like `xxx.p8.png`, it writes a new cart with a name like `xxx_fmt.p8`.

I don't recommend using this tool when publishing your games. Statistically, you will run out of tokens before you run out of characters, and minifying is unlikely to affect the compressed character count. Carts are more useful to the Pico-8 community if the code in a published cart is readable and well-commented. I only wrote `luamin` because it's an obvious kind of code transformation to try with the library.

```
% ./picotool-master/p8tool luamin helloworld.p8.png 
% cat helloworld_fmt.p8
pico-8 cartridge // http://www.pico-8.com
version 5
__lua__
a = 0
music(0)
function _update()
a += 1
end
function _draw()
cls()
...
```


### p8tool listtokens

The `listtokens` tool is similar to `listlua`, but it identifies which characters picotool recognizes as a single token.

```
% ./picotool-master/p8tool listtokens ./picotool-master/tests/testdata/helloworld.p8.png 
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

**Note:** picotool does not currently count tokens the same way Pico-8 does. One purpose of `listtokens` is to help troubleshoot and fix this discrepancy. See "Known issues."


### p8tool printast

The `printast` tool prints a visualization of the abstract syntax tree (AST) determined by the parser. This is a representation of the structure of the Lua code. This is useful for understanding the AST structure when writing a new tool based on the picotool library.

```
% ./picotool-master/p8tool printast ./picotool-master/tests/testdata/helloworld.p8.png 

Chunk
  * stats: [list:]
    - StatAssignment
      * varlist: VarList
        * vars: [list:]
          - VarName
            * name: TokName<'t', line 3 char 0>
      * explist: ExpList
        * exps: [list:]
          - ExpValue
            * value: 0
    - StatFunctionCall
      * functioncall: FunctionCall
        * exp_prefix: VarName
          * name: TokName<'music', line 5 char 0>
        * args: FunctionArgs
          * explist: ExpList
            * exps: [list:]
              - ExpValue
                * value: 0
    - StatFunction
      * funcname: FunctionName
        * namepath: [list:]
          - TokName<'_update', line 7 char 9>
        * methodname: None
      * funcbody: FunctionBody
        * parlist: None
        * dots: None
        * block: Chunk

...
```


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

Lua code is treated as bytestrings throughout the API. This is because Pico-8 uses a custom text encoding equivalent to lower ASCII plus arbitrary high characters for the glyph set. Take care to use b'bytestring literals' when creating or comparing values.


### API under construction!

While the library in its current state is featureful enough for building simple tools, it is not yet ready to promise backwards compatibility in future releases. Feel free to mess with it, but please be patient if I change things.


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

* picotool and Pico-8 count tokens in slightly different ways, resulting in different counts. More refinement is needed so that picotool matches Pico-8. As far as I can tell, with picotool making some concessions to match Pico-8 in known cases, Pico-8's counts are consistently higher. So I'm missing a few cases where Pico-8 over-counts (or picotool under-counts). In most cases, the difference is only by a few tokens, even for large carts.
* Lua allows parentheses to be omitted from a function call if there is exactly one argument and the argument is a string or table literal. picotool does not yet support this case. Pico-8 supports it and offers a one-token discount compared to a similar call with parentheses.
* I've found a few very obscure cases where picotool rejects a cart with a syntax error but Pico-8 accepts it (13757, 16983, 18012, 18556). I evaluate these based on their rarity, usefulness, and intrusiveness to support, and for now I'm leaving this as is.

For more known issues, see the issues list in the Github project: https://github.com/dansanderson/picotool/issues
