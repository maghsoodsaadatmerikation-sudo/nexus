#!/usr/bin/env python3
"""Bounded lossless PNG canonical RGBA digest, stdlib only.

Render may legitimately rewrite PNG container/compression bytes. This decoder
compares actual 8-bit RGBA pixels rather than trusting provider-transformed
source byte equality. Rejects unsupported/interlaced PNG fail-closed.
"""
from __future__ import annotations
import hashlib
import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def pixel_digest(data: bytes, width: int, height: int) -> str:
    if not (1 <= width <= 512 and 1 <= height <= 512
            and SIGNATURE == data[:8] and len(data) < 100_000):
        raise ValueError("untrusted-png-signature-or-size")
    pos = 8
    header = None
    palette = b""
    transparency = b""
    compressed = bytearray()
    completed = False
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError("truncated-png-chunk")
        size = struct.unpack(">I", data[pos:pos+4])[0]
        typ = data[pos+4:pos+8]
        end = pos + 12 + size
        if size > 100_000 or end > len(data):
            raise ValueError("oversized-or-truncated-chunk")
        value = data[pos+8:pos+8+size]
        crc = struct.unpack(">I", data[pos+8+size:end])[0]
        if zlib.crc32(typ + value) & 0xffffffff != crc:
            raise ValueError("invalid-png-chunk-crc")
        if typ == b"IHDR":
            if header is not None or len(value) != 13:
                raise ValueError("duplicate-or-invalid-header")
            w, h, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", value)
            if (w, h) != (width, height) or compression or filtering or interlace:
                raise ValueError("unsupported-png-dimensions-or-interlace")
            if color not in (0, 2, 3, 6) or (
                color in (0, 2, 6) and depth != 8
            ) or (color == 3 and depth not in (1, 2, 4, 8)):
                raise ValueError("unsupported-png-color-depth")
            header = (depth, color)
        elif typ == b"PLTE":
            if len(value) == 0 or len(value) % 3 or len(value) > 768:
                raise ValueError("invalid-palette")
            palette = value
        elif typ == b"tRNS":
            transparency = value
        elif typ == b"IDAT":
            compressed.extend(value)
            if len(compressed) > 100_000:
                raise ValueError("oversized-idat")
        elif typ == b"IEND":
            if size != 0:
                raise ValueError("invalid-iend")
            completed = True
            break
        elif typ and typ[:1].isupper():
            raise ValueError("unknown-critical-png-chunk")
        pos = end
    if not completed or header is None or not compressed:
        raise ValueError("incomplete-png")
    depth, color = header
    if (color == 6 and transparency) or (color == 0 and len(transparency) not in (0, 2)) or (color == 2 and len(transparency) not in (0, 6)):
        raise ValueError("invalid-transparency")
    if color == 3 and (not palette or len(transparency) > len(palette)//3):
        raise ValueError("invalid-palette-transparency")
    transparent = struct.unpack(">" + "H"*(len(transparency)//2), transparency) if color in (0, 2) else ()
    channels = {0: 1, 2: 3, 3: 1, 6: 4}[color]
    row_size = (width * depth * channels + 7) // 8
    byte_stride = max(1, (depth * channels + 7) // 8)
    expected = (row_size + 1) * height
    decompress = zlib.decompressobj()
    raw = decompress.decompress(bytes(compressed), expected + 1)
    # Do not flush an attacker-controlled expansion beyond the output bound.
    if decompress.unconsumed_tail or len(raw) > expected:
        raise ValueError("oversized-png-expansion")
    if len(raw) != expected or not decompress.eof or decompress.unused_data:
        raise ValueError("unexpected-png-uncompressed-length")
    rgba_hash = hashlib.sha256()
    prev = bytes(row_size)
    offset = 0
    for _ in range(height):
        mode = raw[offset]
        offset += 1
        packed = bytearray(raw[offset:offset+row_size])
        offset += row_size
        if mode > 4:
            raise ValueError("invalid-png-filter")
        for x in range(row_size):
            a = packed[x-byte_stride] if x >= byte_stride else 0
            b = prev[x]
            c = prev[x-byte_stride] if x >= byte_stride else 0
            if mode == 0:
                predict = 0
            elif mode == 1:
                predict = a
            elif mode == 2:
                predict = b
            elif mode == 3:
                predict = (a+b)//2
            else:
                p = a+b-c
                d = (abs(p-a), abs(p-b), abs(p-c))
                predict = (a, b, c)[d.index(min(d))]
            packed[x] = (packed[x] + predict) & 255
        prev = bytes(packed)
        line = bytearray()
        if color == 2:
            for x in range(width):
                rgb = packed[x*3:x*3+3]
                line.extend(rgb)
                line.append(0 if tuple(rgb) == transparent else 255)
        elif color == 6:
            line.extend(packed)
        elif color == 0:
            for value in packed:
                line.extend((value, value, value, 0 if (value,) == transparent else 255))
        else:
            if not palette:
                raise ValueError("palette-missing")
            mask = (1 << depth)-1
            for x in range(width):
                bit_index = x * depth
                index = (packed[bit_index//8] >> (8-depth-(bit_index % 8))) & mask
                if 3*index+3 > len(palette):
                    raise ValueError("palette-index-out-of-range")
                line.extend(palette[index*3:index*3+3])
                line.append(transparency[index] if index < len(transparency) else 255)
        if len(line) != width * 4:
            raise ValueError("invalid-png-row")
        rgba_hash.update(line)
    return rgba_hash.hexdigest()
