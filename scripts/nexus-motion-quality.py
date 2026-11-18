#!/usr/bin/env python3
"""Read-only NEXUS Motion technical MP4 quality control.

Validates container, frame count, timestamps, codec, dimensions, audio coverage
and hashes the file. It does NOT rate cinematography, neural realism,
resolution-dependent artistic quality, or grant release/upload authority.
Packet counting scans metadata, not all decoded pixels: a bitstream integrity
decode is outside this technical acceptance boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

class QualityError(ValueError):
    pass


def demand(ok: bool, message: str) -> None:
    if not ok:
        raise QualityError(message)


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def get_probe(path: Path) -> dict:
    demand(path.is_file() and not path.is_symlink() and path.suffix.lower() == ".mp4"
           and path.stat().st_size > 500, "missing, linked or empty MP4")
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-count_packets", "-show_entries",
             "format=duration,size,format_name:stream=index,codec_type,codec_name,"
             "width,height,pix_fmt,avg_frame_rate,start_time,duration,"
             "nb_read_packets,sample_rate,channels", "-of", "json", str(path)],
            capture_output=True, check=True, timeout=90,
        )
        data = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise QualityError("ffprobe failed or produced invalid output") from exc
    demand(type(data) is dict and type(data.get("streams")) is list
           and type(data.get("format")) is dict, "ffprobe report incomplete")
    return data


def integer_text(value: object, *, min_value: int = 0) -> int:
    demand(type(value) is str and value.isascii() and value.isdecimal()
           and 1 <= len(value) <= 18 and (len(value) == 1 or value[0] != "0"),
           "missing or noncanonical container packet count")
    n = int(value)
    demand(n >= min_value, "invalid packet count")
    return n


def fraction(value: object) -> float:
    demand(type(value) is str and "/" in value, "invalid frame rate ratio")
    try:
        numerator, denominator = value.split("/")
        n, d = int(numerator), int(denominator)
        demand(n >= 0 and d > 0, "invalid frame rate numerator/denominator")
        return n / d
    except (ValueError, ZeroDivisionError) as exc:
        raise QualityError("invalid frame rate ratio") from exc


def seconds(value: object) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise QualityError("invalid media timestamp") from exc
    demand(out == out and abs(out) < 100000, "non-finite/oversized media timestamp")
    return out


def check(path: Path, *, width: int, height: int, fps: int,
          duration: int, require_audio: bool) -> dict:
    demand(type(width) is int and type(height) is int
           and (width, height) in {(1280,720),(1920,1080),(3840,2160),
                                   (1080,1920),(2160,3840)}, "unsupported output resolution")
    demand(type(fps) is int and fps in {24,25,30,60}
           and type(duration) is int and 1 <= duration <= 7200,
           "unsupported timing contract")
    demand(type(require_audio) is bool, "audio contract must be boolean")
    data = get_probe(path)
    tracks = data["streams"]
    video = [s for s in tracks if type(s) is dict and s.get("codec_type") == "video"]
    audio = [s for s in tracks if type(s) is dict and s.get("codec_type") == "audio"]
    demand(len(video) == 1 and len(audio) == int(require_audio)
           and len(video) + len(audio) == len(tracks),
           "missing, duplicate or unexpected media streams")
    v = video[0]
    demand(v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p"
           and v.get("width") == width and v.get("height") == height,
           "H.264 codec, pixel format or video dimensions mismatch")
    demand(abs(fraction(v.get("avg_frame_rate")) - fps) < 1e-9,
           "output frame rate differs from storyboard")
    count = integer_text(v.get("nb_read_packets"), min_value=1)
    expected = duration * fps
    demand(count == expected,
           f"frame packet count mismatch: {count} != {expected}")
    tolerance = max(0.1, 2 / fps)
    video_start = seconds(v.get("start_time"))
    video_duration = seconds(v.get("duration"))
    mux_duration = seconds(data["format"].get("duration"))
    demand(abs(video_start) <= tolerance and abs(video_duration - duration) <= tolerance
           and abs(mux_duration - duration) <= tolerance,
           "truncated or shifted container/video timestamps")
    sound_info = None
    if require_audio:
        s = audio[0]
        demand(s.get("codec_name") == "aac", "soundtrack must use AAC")
        demand(integer_text(s.get("nb_read_packets"), min_value=1) > 0,
               "AAC stream contains no packets")
        channels = s.get("channels")
        sample_rate = integer_text(s.get("sample_rate"), min_value=8000)
        demand(type(channels) is int and channels in {1,2}
               and sample_rate <= 192000, "unsupported AAC channels/sample rate")
        audio_start = seconds(s.get("start_time"))
        audio_duration = seconds(s.get("duration"))
        demand(abs(audio_start) <= 0.15
               and abs(audio_duration - duration) <= 0.25,
               "soundtrack lacks expected coverage or begins too late")
        sound_info = {"codec": "aac", "channels": channels, "sample_rate": sample_rate,
                      "start_seconds": audio_start, "duration_seconds": audio_duration}

    return {"schema": "nexus.motion.technical-qc.v1",
            "status": "TECHNICAL_MP4_VERIFIED",
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "width": width, "height": height, "fps": fps,
            "expected_frames": expected, "verified_video_packets": count,
            "duration_seconds": duration, "audio": sound_info,
            "full_video_decode_performed": False,
            "artistic_quality_assessed": False,
            "photorealistic_ai_model_used": False,
            "release_authorized": False, "upload_performed": False}


def main() -> int:
    p = argparse.ArgumentParser(description="NEXUS Motion local MP4 technical QC")
    p.add_argument("mp4", type=Path)
    p.add_argument("--width", required=True, type=int)
    p.add_argument("--height", required=True, type=int)
    p.add_argument("--fps", required=True, type=int)
    p.add_argument("--duration", required=True, type=int)
    p.add_argument("--audio", action="store_true")
    x = p.parse_args()
    try:
        result = check(x.mp4, width=x.width, height=x.height,
                       fps=x.fps, duration=x.duration, require_audio=x.audio)
    except (OSError, QualityError) as exc:
        print("NEXUS MOTION QC: DENIED (" + str(exc) + ")", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
