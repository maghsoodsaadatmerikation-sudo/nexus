#!/usr/bin/env python3
"""Build Nexus icons from the approved indexed artwork."""

import argparse
import base64
import json
from pathlib import Path
import re
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "assets/branding/nexus-logo-source.json"
SIZE = 64
GATEWAY_ICON = re.compile(r"<link rel=\"icon\" type=\"image/png\" href=\"data:image/png;base64,[A-Za-z0-9+/=]+\" >|<!-- NEXUS_GATEWAY_FAVICON -->")


def artwork():
    source = json.loads(MASTER.read_text())
    if source["schema"] != "nexus.brand.rle.v1" or (source["width"], source["height"]) != (SIZE, SIZE):
        raise ValueError("unsupported logo source")
    palette = bytes.fromhex(source["palette_rgb"])
    if len(palette) != 32 * 3:
        raise ValueError("logo needs the approved 32-color palette")
    packed = base64.b64decode(source["rle"], validate=True)
    if len(packed) % 3:
        raise ValueError("truncated logo record")
    pixels = bytearray()
    for i in range(0, len(packed), 3):
        block = int.from_bytes(packed[i:i+3], "big")
        for run in (block >> 12, block & 0xfff):
            if run & 0x20:
                raise ValueError("unsupported logo run flag")
            pixels.extend(bytes([run & 31]) * ((run >> 6) + 1))
    if len(pixels) != SIZE * SIZE:
        raise ValueError("logo pixel count mismatch")
    return bytes(pixels), palette


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(size, pixels, palette=None):
    channels = 1 if palette else 3
    stride = size * channels
    rows = []
    for offset in range(0, len(pixels), stride):
        row = pixels[offset:offset+stride]
        if palette:
            rows.append(b"\0" + row)
        else:
            deltas = bytes((right - left) & 255 for left, right in zip(row, row[3:]))
            rows.append(b"\1" + row[:3] + deltas)
    scan = b"".join(rows)
    header = struct.pack(">IIBBBBB", size, size, 8, 3 if palette else 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
            (chunk(b"PLTE", palette) if palette else b"") +
            chunk(b"IDAT", zlib.compress(scan, 9)) + chunk(b"IEND", b""))


def resized(indices, palette, size):
    # Center-aligned bilinear resampling with integer weights.
    edge = 2 * size
    positions = [divmod(max(0, min((2*i+1)*SIZE-size, (SIZE-1)*edge)), edge) for i in range(size)]
    rgb = [tuple(palette[index*3:index*3+3]) for index in indices]
    result = bytearray()
    for y, dy in positions:
        bottom = min(y + 1, SIZE - 1)
        for x, dx in positions:
            right = min(x + 1, SIZE - 1)
            upper_left, upper_right = rgb[y*SIZE+x], rgb[y*SIZE+right]
            lower_left, lower_right = rgb[bottom*SIZE+x], rgb[bottom*SIZE+right]
            for a, b, c, d in zip(upper_left, upper_right, lower_left, lower_right):
                top = a*(edge-dx) + b*dx
                base = c*(edge-dx) + d*dx
                result.append((top*(edge-dy) + base*dy + edge*edge//2) // (edge*edge))
    return bytes(result)


def outputs():
    indices, palette = artwork()
    inline = png(SIZE, indices, palette)
    icon192 = png(192, resized(indices, palette, 192))
    icon512 = png(512, resized(indices, palette, 512))
    gateway = (ROOT / "web/index.html").read_text()
    uri = base64.b64encode(inline).decode("ascii")
    favicon = f'<link rel="icon" type="image/png" href="data:image/png;base64,{uri}" >'
    gateway, count = GATEWAY_ICON.subn(favicon, gateway)
    if count != 1:
        raise ValueError("gateway has an invalid brand slot")
    return {
        "web/index.html": gateway.encode(),
        "web/nexus-brand-icon.png": inline,
        "public/icons/nexus-192.png": icon192,
        "public/icons/nexus-512.png": icon512,
        "android/app/src/main/res/drawable-nodpi/nexus_icon.png": icon192,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, expected in outputs().items():
        target = ROOT / path
        if args.check:
            if not target.is_file() or target.read_bytes() != expected:
                raise SystemExit(f"stale Nexus brand asset: {path}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)


if __name__ == "__main__":
    main()
