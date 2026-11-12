#!/usr/bin/env python3
"""Public icon integrity regressions: compare pixels, retain strict code bytes."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest
import zlib
from png_pixels import pixel_digest

spec = importlib.util.spec_from_file_location(
    "observer", Path(__file__).with_name("verify-public-pwa-assets.py"))
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def chunk(kind, value):
    return (struct.pack(">I", len(value)) + kind + value
            + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff))


def png(color=6, pixels=b"\x20\x40\x60\xff", extras=(), level=6, raw=None):
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(
        ">IIBBBBB", 1, 1, 8, color, 0, 0, 0))
        + b"".join(chunk(k, v) for k, v in extras)
        + chunk(b"IDAT", zlib.compress(b"\0" + pixels if raw is None else raw, level))
        + chunk(b"IEND", b""))


class IntegrityTests(unittest.TestCase):
    def test_recompressed_icon_keeps_exact_pixels(self):
        a, b = png(level=0), png(level=9)
        self.assertNotEqual(a, b)
        report = observer.compare(200, "image/png", b, a, "image/png", 1)
        self.assertTrue(report["ok"])
        self.assertFalse(report["exact_byte_match"])
        self.assertTrue(report["pixel_match"])

    def test_changed_pixel_or_alpha_is_rejected(self):
        for p in (b"\x21\x40\x60\xff", b"\x20\x40\x60\x00"):
            self.assertFalse(observer.compare(
                200, "image/png", png(pixels=p), png(), "image/png", 1)["ok"])

    def test_palette_representation_is_equivalent(self):
        p = png(color=3, pixels=b"\0", extras=[(b"PLTE", b"\x20\x40\x60")])
        self.assertEqual(pixel_digest(p, 1, 1), pixel_digest(png(), 1, 1))

    def test_palette_transparency_is_preserved(self):
        p = png(color=3, pixels=b"\0", extras=[
            (b"PLTE", b"\x20\x40\x60"), (b"tRNS", b"\x80")])
        self.assertEqual(pixel_digest(p, 1, 1),
                         pixel_digest(png(pixels=b"\x20\x40\x60\x80"), 1, 1))

    def test_truecolor_and_grayscale_transparency(self):
        for color, pixels, trans, rgba in [
            (2, b"\x20\x40\x60", struct.pack(">HHH", 32, 64, 96), b"\x20\x40\x60\0"),
            (0, b"\x20", struct.pack(">H", 32), b"\x20\x20\x20\0")]:
            p = png(color=color, pixels=pixels, extras=[(b"tRNS", trans)])
            self.assertEqual(pixel_digest(p, 1, 1), hashlib.sha256(rgba).hexdigest())

    def test_invalid_or_oversized_stream_is_rejected(self):
        bad = bytearray(png()); bad[-1] ^= 1
        for p in (bytes(bad), png()[:-5], png(raw=b"\0" * 2_000_000)):
            with self.assertRaises(ValueError):
                pixel_digest(p, 1, 1)

    def test_mime_status_and_dimensions_still_fail_closed(self):
        for status, mime, size in [(302, "image/png", 1),
                                   (200, "text/html", 1), (200, "image/png", 2)]:
            self.assertFalse(observer.compare(status, mime, png(), png(), "image/png", size)["ok"])

    def test_code_and_manifest_require_exact_bytes(self):
        for kind, mime in [("text/html", "text/html"),
                           ("manifest", "application/json"),
                           ("javascript", "text/javascript")]:
            self.assertFalse(observer.compare(200, mime, b"changed", b"source", kind)["ok"])


if __name__ == "__main__":
    unittest.main()
