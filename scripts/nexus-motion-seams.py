#!/usr/bin/env python3
"""NEXUS Motion: bounded frame-to-frame seam audit for an existing local MP4.

A seam is the last decoded frame of scene N versus the first of scene N+1.
The luminance mean absolute difference is an EDITORIAL WARNING, not a failure.
Intentional cuts, bright flashes and fades can affect the score. No automatic
smoothing, face alteration, network, uploading or public release is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nexus_motion_seam_renderer", ROOT / "nexus-motion-render.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
FRAME_W, FRAME_H = 64, 36
FRAME_BYTES = FRAME_W * FRAME_H
MAX_SEAMS = 24
WARNING_SCORE = .24


def require(ok: bool, message: str) -> None:
    base.require(ok, message)


def sample_indices(count: int, limit: int = MAX_SEAMS) -> list[int]:
    """1-based scene boundary indices, including earliest/latest when sampled."""
    require(type(count) is int and 1 <= count <= 120, "invalid scene count")
    require(type(limit) is int and 1 <= limit <= MAX_SEAMS, "invalid seam sample limit")
    boundaries = count - 1
    if boundaries == 0:
        return []
    if boundaries <= limit:
        return list(range(1, count))
    if limit == 1:
        return [1]
    indices = [1 + round(k * (boundaries - 1) / (limit - 1)) for k in range(limit)]
    require(len(set(indices)) == limit, "seam sampling failed to keep distinct indices")
    return indices


def one_gray_frame(path: Path, *, frame_index: int, fps: int) -> bytes:
    """Extract one low-res decoded frame at an exact integer frame index."""
    require(type(frame_index) is int and frame_index >= 0
            and type(fps) is int and fps in (24, 25, 30, 60),
            "invalid frame selection")
    t = frame_index / fps
    # Input seek with accurate-seek enabled. Keep the seek timestamp slightly
    # inside the desired frame; avoid boundary floating point rounding.
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error",
           "-ss", f"{t + .10 / fps:.9f}", "-protocol_whitelist", "file,pipe",
           "-i", str(path), "-frames:v", "1",
           "-vf", f"scale={FRAME_W}:{FRAME_H}:flags=area,format=gray",
           "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=45)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise base.MotionError("local seam frame decode failed") from exc
    require(len(result.stdout) == FRAME_BYTES,
            "frame decoder returned no frame or unexpected pixel size")
    return result.stdout


def average_luminance_difference(a: bytes, b: bytes) -> float:
    require(type(a) is bytes and type(b) is bytes
            and len(a) == FRAME_BYTES and len(b) == FRAME_BYTES,
            "incompatible decoded luminance frames")
    return sum(abs(x - y) for x, y in zip(a, b)) / (FRAME_BYTES * 255)


def scan(path: Path, story: dict, *, max_seams: int = MAX_SEAMS) -> dict:
    require(path.is_file() and not path.is_symlink() and path.suffix.lower() == ".mp4"
            and path.stat().st_size > 500, "unsafe or empty output movie")
    require(shutil.which("ffmpeg") is not None, "FFmpeg is not installed")
    require(type(story) is dict and type(story.get("scenes")) is list
            and type(story.get("fps")) is int and story["fps"] in (24,25,30,60),
            "unsupported project timeline")
    scenes = story["scenes"]
    require(1 <= len(scenes) <= 120, "unsupported scene count")
    fps = story["fps"]
    durations = []
    for scene in scenes:
        require(type(scene) is dict and type(scene.get("duration")) is int
                and 1 <= scene["duration"] <= 900, "invalid scene duration")
        durations.append(scene["duration"])
    require(sum(durations) <= 7200, "unsupported project length")
    selected = sample_indices(len(scenes), max_seams)
    boundaries = []
    running = 0
    selected_set = set(selected)
    for idx, sec in enumerate(durations, start=1):
        running += sec
        if idx not in selected_set:
            continue
        last_index = running * fps - 1
        first_index = running * fps
        before = one_gray_frame(path, frame_index=last_index, fps=fps)
        after = one_gray_frame(path, frame_index=first_index, fps=fps)
        score = average_luminance_difference(before, after)
        boundaries.append({
            "boundary_after_scene": idx, "second": running,
            "preceding_frame_index": last_index, "following_frame_index": first_index,
            "luma_mae": round(score, 6),
            "editor_review_suggested": score >= WARNING_SCORE,
        })
    return {
        "schema": "nexus.motion.scene-seam-diagnostics.v1",
        "status": "ADVISORY_ONLY",
        "video_bytes": path.stat().st_size,
        "fps": fps, "duration_seconds": sum(durations),
        "total_scene_boundaries": max(0, len(scenes) - 1),
        "sampled_boundaries": len(boundaries),
        "sampling_limited_to": MAX_SEAMS,
        "warning_score_luma_mae": WARNING_SCORE,
        "seams": boundaries,
        "boundaries_flagged": sum(1 for x in boundaries if x["editor_review_suggested"]),
        "review_suggested": any(x["editor_review_suggested"] for x in boundaries),
        "frames_decoded_outside_seams": False,
        "full_video_quality_assessed": False,
        "pixel_parity_with_canvas_proven": False,
        "intentional_cuts_may_be_flagged": True,
        "render_failure": False,
        "upload_performed": False,
        "release_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="NEXUS Motion local scene seam warning report")
    parser.add_argument("storyboard", type=Path, help="local JSON or browser ZIP with assets")
    parser.add_argument("movie", type=Path, help="local completed .mp4 movie")
    parser.add_argument("--max-seams", type=int, default=MAX_SEAMS, help="1-24 boundaries")
    args = parser.parse_args()
    try:
        with base.project_source(args.storyboard) as project:
            story = base.load_project(project)
            output = scan(args.movie, story, max_seams=args.max_seams)
        print(json.dumps(output, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, ValueError, base.MotionError) as exc:
        print("NEXUS MOTION SEAMS: DENIED (" + str(exc) + ")", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
