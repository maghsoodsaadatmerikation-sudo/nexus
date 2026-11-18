#!/usr/bin/env python3
"""NEXUS Motion: honest local resource estimate and sampled visual diagnostics.

Neither plan estimates nor black/freeze warnings are a quality guarantee.
No upload, neural model, CUDA allocation, network, or automatic deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("nexus_motion_render_for_diagnostics", ROOT / "nexus-motion-render.py")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
MIB = 1024 * 1024
GIB = 1024 * MIB
MINIMUM_FREE = 128 * MIB
VISUAL_FILTER = "scale=320:-2,blackdetect=d=0.4:pix_th=0.07,freezedetect=n=-50dB:d=1.0"
BLACK = re.compile(r"black_start:(?:-?\d+(?:\.\d+)?)")
FREEZE = re.compile(r"freeze_start:\s*(?:-?\d+(?:\.\d+)?)")


def need(ok: bool, msg: str) -> None:
    BASE.require(ok, msg)


def bounded_storyboard(story: dict) -> None:
    need(type(story) is dict and type(story.get("scenes")) is list
         and 1 <= len(story["scenes"]) <= 120
         and story.get("schema") == BASE.SCHEMA, "invalid storyboard schema")
    need(type(story.get("width")) is int and type(story.get("height")) is int
         and (story["width"], story["height"]) in BASE.DIMENSIONS,
         "unsupported image dimensions")
    need(type(story.get("fps")) is int and story["fps"] in (24,25,30,60),
         "unsupported frame rate")
    seconds = 0
    for scene in story["scenes"]:
        need(type(scene) is dict and type(scene.get("duration")) is int
             and 1 <= scene["duration"] <= 900, "unsupported scene duration")
        seconds += scene["duration"]
    need(seconds <= 7200, "project duration exceeds current supported limit")


def plan(story: dict, *, free_disk_bytes: int) -> dict:
    """Planning estimate from assumed bitrate, NOT upper or lower size bound."""
    bounded_storyboard(story)
    need(type(free_disk_bytes) is int and free_disk_bytes >= 0,
         "available storage must be an integer number of bytes")
    width, height, fps = story["width"], story["height"], story["fps"]
    duration = sum(scene["duration"] for scene in story["scenes"])
    total_frames = fps * duration
    # 12 Mbps at 1080p30, linearly scaled by pixels and fps. This is a
    # *planning assumption*, not a guaranteed actual libx264 bitrate.
    assumed_bps = math.ceil(12_000_000 * width * height * fps / (1920 * 1080 * 30))
    expected_video = math.ceil(assumed_bps * duration / 8)
    soundtrack = bool(story.get("soundtrack"))
    expected_audio = 32_000 * duration if soundtrack else 0  # 256 kbps AAC
    # Retained scene cache + joined MP4 + muxed MP4 (audio jobs only).
    # Output and cache must be on the same local volume to use this estimate.
    stages = 3 if soundtrack else 2
    safety = 512 * MIB + min(2 * GIB, expected_video // 4)
    recommended = stages * expected_video + expected_audio + safety
    return {
        "schema": "nexus.motion.resource-estimate.v1",
        "status": "ADVISORY_ESTIMATE_ONLY",
        "dimensions": [width, height],
        "fps": fps,
        "duration_seconds": duration,
        "scenes": len(story["scenes"]),
        "total_expected_frames": total_frames,
        "uncompressed_single_rgba_frame_bytes": width * height * 4,
        "assumed_h264_bitrate_mbps": round(assumed_bps / 1_000_000, 2),
        "estimated_video_bytes": expected_video,
        "estimated_audio_bytes": expected_audio,
        "estimated_peak_local_bytes": recommended,
        "available_local_bytes": free_disk_bytes,
        "free_space_below_recommendation": free_disk_bytes < recommended,
        "below_absolute_minimum_128mib": free_disk_bytes < MINIMUM_FREE,
        "size_estimate_is_hard_upper_bound": False,
        "render_speed_guaranteed": False,
        "android_thermal_test_performed": False,
        "external_gpu_allocated": False,
        "recommended_action": (
            "STOP_UNDER_ABSOLUTE_MINIMUM" if free_disk_bytes < MINIMUM_FREE
            else "REVIEW_SPACE_AND_USE_SHORT_MANUAL_BATCHES"
            if free_disk_bytes < recommended else "CAPACITY_ESTIMATE_NOT_EXCEEDED"
        ),
        "suggested_max_new_scenes_per_batch": (
            1 if width * height >= 3840 * 2160
            else 3 if width * height >= 1920 * 1080 else 5
        ),
        "release_authorized": False,
        "upload_performed": False,
    }


def sample_offsets(duration: int, width: int = 2) -> list[int]:
    need(type(duration) is int and 1 <= duration <= 7200, "invalid scan duration")
    need(type(width) is int and width in (1, 2), "invalid scan window")
    tail = max(0, duration - width)
    offsets = [0, max(0, duration // 2 - width // 2), tail]
    return list(dict.fromkeys(offsets))


def scan_visual(path: Path, *, duration: int, window_seconds: int = 2) -> dict:
    """Scan up to three short decoded windows; observations are advisory only.

    Static titles, slow fades and intentionally dark scenes will naturally
    trigger warnings. Do not interpret these as an automated artistic verdict.
    """
    need(path.is_file() and not path.is_symlink() and path.suffix.lower() == ".mp4"
         and path.stat().st_size > 500, "missing or unsafe local MP4")
    need(shutil.which("ffmpeg") is not None, "local FFmpeg executable missing")
    offsets = sample_offsets(duration, window_seconds)
    reports = []
    for offset in offsets:
        length = min(window_seconds, duration - offset)
        cmd = [
            "ffmpeg", "-hide_banner", "-nostdin", "-v", "info",
            "-ss", str(offset), "-protocol_whitelist", "file,pipe", "-i", str(path),
            "-t", str(length), "-vf", VISUAL_FILTER, "-an", "-f", "null", "-",
        ]
        try:
            p = subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=75)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise BASE.MotionError("visual sampler could not complete bounded local decode") from exc
        log = p.stderr.decode("utf-8", "replace")[-300_000:]
        black = len(BLACK.findall(log))
        frozen = len(FREEZE.findall(log))
        reports.append({
            "offset_seconds": offset,
            "sampled_seconds": length,
            "black_intervals_observed": black,
            "freeze_intervals_observed": frozen,
            "review_suggested": (black + frozen) > 0,
        })
    flags = sum(int(x["review_suggested"]) for x in reports)
    return {
        "schema": "nexus.motion.sampled-visual-audit.v1",
        "status": "ADVISORY_ONLY",
        "file_bytes": path.stat().st_size,
        "duration_seconds": duration,
        "sampling_windows": reports,
        "review_suggested": flags > 0,
        "windows_flagged": flags,
        "entire_video_scanned": False,
        "color_motion_parity_verified": False,
        "artistic_quality_assessed": False,
        "warning_is_render_failure": False,
        "release_authorized": False,
        "upload_performed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="NEXUS Motion local resource and visual advisory")
    sub = p.add_subparsers(dest="operation", required=True)
    plan_cmd = sub.add_parser("plan", help="Estimate peak staging disk from a local project")
    plan_cmd.add_argument("project", type=Path)
    plan_cmd.add_argument("--output-dir", type=Path, default=Path("."))
    scan_cmd = sub.add_parser("scan", help="Sample start/middle/end of an existing MP4")
    scan_cmd.add_argument("movie", type=Path)
    scan_cmd.add_argument("--duration", type=int, required=True)
    try:
        args = p.parse_args()
        if args.operation == "plan":
            need(args.output_dir.is_dir() and not args.output_dir.is_symlink(),
                 "output directory must be a real existing local directory")
            with BASE.project_source(args.project) as path:
                story = BASE.load_project(path)
                result = plan(story, free_disk_bytes=shutil.disk_usage(args.output_dir).free)
        else:
            result = scan_visual(args.movie, duration=args.duration)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (BASE.MotionError, OSError, ValueError) as exc:
        print(f"NEXUS MOTION DIAGNOSTICS: DENIED ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
