"""PICO-8 Lua compression routines"""

__all__ = [
    'compress_code',
    'decompress_code',
]

COMPRESSED_LUA_CHAR_TABLE = list(
    b'#\n 0123456789abcdefghijklmnopqrstuvwxyz!#%(){}[]<>+=/*:;.,~_')

# PICO-8 adds this automatically to compressed code and removes it
# automatically from decompressed code to maintain compatibility with PICO-8
# 0.1.7.
PICO8_FUTURE_CODE1 = (b'if(_update60)_update=function()'
                      b'_update60()_update60()end')
PICO8_FUTURE_CODE2 = (b'if(_update60)_update=function()'
                      b'_update60()_update_buttons()_update60()end')


def _find_repeatable_block(dat, pos):
    """Find a repeatable block in the data.

    Part of the literal port of the PICO-8 compression routine. See
    compress_code().

    Args:
        dat: Array of data bytes.
        pos: Starting index in dat.

    Returns:
        A tuple: (best_len, block_offset)
    """
    max_block_len = 17
    max_hist_len = (255 - len(COMPRESSED_LUA_CHAR_TABLE)) * 16
    best_len = 0
    best_i = -100000

    max_len = min(max_block_len, len(dat) - pos)
    max_hist_len = min(max_hist_len, pos)

    i = pos - max_hist_len
    while i < pos:
        j = i
        while (j - i) < max_len and j < pos and dat[j] == dat[pos + j - i]:
            j += 1

        if (j - i) > best_len:
            best_len = j - i
            best_i = i

        i += 1

    block_offset = pos - best_i

    return best_len, block_offset


def compress_code(in_p):
    """A literal port of the PICO-8 C compression routine.

    TODO: The original algorithm uses a brute force search for blocks
    (_find_repeatable_block()), which makes the overall algorithm O(n^2).
    I had a previous implementation that was faster but did not produce
    the same compressed result. It should be possible to optimize the
    working implementation using Python features without changing its
    result. (A quick attempt at memoization did not result in a speed
    increase.)

    Args:
        in_p: The code to compress, as a bytestring.

    Returns:
        The compressed code, as a bytearray. The compressed result is
        returned even if it is longer than in_p. The caller is responsible
        for comparing it to the original and acting accordingly.
    """
    PICO8_CODE_ALLOC_SIZE = (0x10000 + 1)
    pos = 0

    literal_index = [0] * 256
    for i in range(1, len(COMPRESSED_LUA_CHAR_TABLE)):
        literal_index[COMPRESSED_LUA_CHAR_TABLE[i]] = i

    if b'_update60' in in_p and len(in_p) < PICO8_CODE_ALLOC_SIZE - (
            len(PICO8_FUTURE_CODE2) + 1):
        if in_p[-1] != b' '[0] and in_p[-1] != b'\n'[0]:
            in_p += b'\n'
        in_p += PICO8_FUTURE_CODE2

    out = bytearray()

    # The PICO-8 C code adds the preamble here, but we do it in
    # get_bytes_from_code().
    # out += b':c:\x00'
    # out.append(len(in_p) // 256)
    # out.append(len(in_p) % 256)
    # out += b'\x00\x00'

    while pos < len(in_p):
        block_len, block_offset = _find_repeatable_block(in_p, pos)

        if block_len >= 3:
            out.append(
                (block_offset // 16) + len(COMPRESSED_LUA_CHAR_TABLE))
            out.append((block_offset % 16) + (block_len - 2) * 16)
            pos += block_len
        else:
            out.append(literal_index[in_p[pos]])
            if literal_index[in_p[pos]] == 0:
                out.append(in_p[pos])
            pos += 1

    return out


def decompress_code(codedata):
    """Decompresses compressed code data.

    Args:
        codedata: The bytes of the code region (0x4300:0x8000).

    Returns:
        The tuple (code_length, code, compressed_size). code is a bytestring.
    """
    code_length = (codedata[4] << 8) | codedata[5]
    assert bytes(codedata[6:8]) == b'\x00\x00'

    out = [0] * code_length
    in_i = 8
    out_i = 0
    while out_i < code_length and in_i < len(codedata):
        if codedata[in_i] == 0x00:
            in_i += 1
            out[out_i] = codedata[in_i]
            out_i += 1
        elif codedata[in_i] <= 0x3b:
            out[out_i] = COMPRESSED_LUA_CHAR_TABLE[codedata[in_i]]
            out_i += 1
        else:
            in_i += 1
            offset = (
                (codedata[in_i - 1] - 0x3c) * 16 +
                (codedata[in_i] & 0xf))
            length = (codedata[in_i] >> 4) + 2
            out[out_i:out_i + length] = \
                out[out_i - offset:out_i - offset + length]
            out_i += length
        in_i += 1

    code = bytes(out).strip(b'\x00')
    if code.endswith(PICO8_FUTURE_CODE1):
        code = code[:-len(PICO8_FUTURE_CODE1)]
        if code[-1] == b'\n'[0]:
            code = code[:-1]
    if code.endswith(PICO8_FUTURE_CODE2):
        code = code[:-len(PICO8_FUTURE_CODE2)]
        if code[-1] == b'\n'[0]:
            code = code[:-1]

    compressed_size = in_i

    return code_length, code, compressed_size
