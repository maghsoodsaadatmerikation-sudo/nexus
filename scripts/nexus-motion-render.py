#!/usr/bin/env python3
"""NEXUS Motion: bounded, local, loss-conscious MP4 storyboard renderer.

No model, account, network, payment, upload, external shell, or inherited
provider credentials. FFmpeg/ffprobe must be installed by the operator.
Scene-by-scene H.264 encoding and concat avoid keeping full 4K frames in RAM.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

SCHEMA = "nexus.motion.storyboard.v1"
DIMENSIONS = {(1280, 720), (1920, 1080), (1080, 1920), (3840, 2160), (2160, 3840)}
MOTIONS = {"still", "push", "pull", "pan-left", "pan-right"}
COLORS = re.compile(r"#[0-9a-fA-F]{6}\Z")
FILES = re.compile(r"[A-Za-z0-9 _().+/@-]{1,180}\Z")
PROJECT_KEYS = {"schema", "title", "width", "height", "fps", "scenes", "soundtrack"}
SCENE_KEYS = {"duration", "background", "accent", "title", "subtitle", "motion", "image"}
CODECS = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}
FONT_CHOICES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
)


class MotionError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise MotionError(message)


def pairs_unique(pairs):
    result = {}
    for k, value in pairs:
        require(k not in result, "duplicate project JSON key")
        result[k] = value
    return result


def load_project(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 256_000,
            "missing, linked or oversized storyboard")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(MotionError("non-finite JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MotionError("invalid project JSON") from exc
    return validate(data, path.parent)


def safe_media(folder: Path, relative: str, extensions: set[str], max_bytes: int) -> Path:
    require(type(relative) is str and FILES.fullmatch(relative) is not None
            and not relative.startswith("/") and "\\" not in relative
            and not any(part in (".", "..") for part in relative.split("/")),
            "invalid media path")
    require(Path(relative).suffix.lower() in extensions, "unsupported media extension")
    root = folder.resolve(strict=True)
    item = folder / relative
    require(item.is_file() and not item.is_symlink(), "media file missing or linked")
    for parent in list(item.parents):
        if parent == folder:
            break
        require(not parent.is_symlink(), "linked media parent is prohibited")
    real = item.resolve(strict=True)
    require(real.is_relative_to(root) and 0 < real.stat().st_size <= max_bytes,
            "media path escapes project or exceeds size budget")
    return real


def safe_text(text, limit):
    require(type(text) is str and 0 < len(text) <= limit and
            all(ord(ch) >= 32 or ch == "\n" for ch in text)
            and "\x00" not in text and "\r" not in text,
            "invalid title/subtitle")
    require(len(text.encode("utf-8")) <= limit * 4, "text bytes exceed limit")
    return text


def validate(raw, project_dir: Path) -> dict:
    require(type(raw) is dict and set(raw) <= PROJECT_KEYS
            and {"schema", "title", "width", "height", "fps", "scenes"} <= set(raw),
            "invalid storyboard fields")
    require(raw["schema"] == SCHEMA, "unknown storyboard schema")
    safe_text(raw["title"], 100)
    w, h, fps = raw["width"], raw["height"], raw["fps"]
    require(type(w) is int and type(h) is int and (w, h) in DIMENSIONS,
            "unsupported frame dimensions")
    require(type(fps) is int and fps in (24, 25, 30, 60), "unsupported frame rate")
    scenes = raw["scenes"]
    require(type(scenes) is list and 1 <= len(scenes) <= 120, "need 1-120 scenes")
    duration = 0
    for scene in scenes:
        require(type(scene) is dict and set(scene) <= SCENE_KEYS
                and {"duration", "background", "accent", "title", "motion"} <= set(scene),
                "unknown or missing scene attributes")
        sec = scene["duration"]
        require(type(sec) is int and 1 <= sec <= 900, "scene duration must be 1-900 seconds")
        duration += sec
        require(type(scene["background"]) is str and COLORS.fullmatch(scene["background"]) is not None,
                "invalid background")
        require(type(scene["accent"]) is str and COLORS.fullmatch(scene["accent"]) is not None,
                "invalid accent")
        safe_text(scene["title"], 120)
        if "subtitle" in scene and scene["subtitle"]:
            safe_text(scene["subtitle"], 180)
        else:
            require("subtitle" not in scene or scene["subtitle"] == "", "invalid subtitle")
        require(scene["motion"] in MOTIONS, "invalid scene motion")
        if "image" in scene and scene["image"]:
            safe_media(project_dir, scene["image"], CODECS, 64 * 1024 * 1024)
    require(duration <= 7200, "storyboard is limited to 2 hours per render")
    if "soundtrack" in raw and raw["soundtrack"]:
        safe_media(project_dir, raw["soundtrack"], AUDIO, 1024 * 1024 * 1024)
    else:
        require("soundtrack" not in raw or raw["soundtrack"] == "", "invalid soundtrack")
    return raw


def ff_filter_path(path: Path) -> str:
    # FFmpeg filtergraph special syntax; the passed filename is generated
    # inside a private, safe temporary directory.
    value = str(path)
    require(all(x not in value for x in "\n\r\x00'\\"), "unsafe temporary path")
    return value.replace(":", "\\:")


def scene_filter(scene: dict, folder: Path, tempdir: Path, index: int,
                 w: int, h: int, fps: int, font: Path) -> str:
    # All FFmpeg text is isolated in UTF-8 files, never interpolated in filters.
    title = tempdir / f"title-{index:03d}.txt"
    title.write_text(scene["title"], encoding="utf-8")
    text = [
        f"scale={w}:{h}:force_original_aspect_ratio=decrease",
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x{scene['background'][1:]}",
        "setsar=1",
    ]
    # Procedural line geometry gives photo-free scenes actual pixel motion
    # when zoom/pan is selected; a uniform color alone cannot visibly move.
    if not scene.get("image"):
        text.append(f"drawgrid=w={max(80,w//8)}:h={max(70,h//6)}:"
                    f"t={max(1,w//800)}:c=0x{scene['accent'][1:]}@0.15")
    motion = scene["motion"]
    if motion != "still":
        length = scene["duration"] * fps
        if motion == "push":
            zoom = f"min(1.10,1+on*0.10/{max(length, 1)})"
            x = "iw/2-(iw/zoom/2)"
        elif motion == "pull":
            zoom = f"max(1,1.10-on*0.10/{max(length, 1)})"
            x = "iw/2-(iw/zoom/2)"
        else:
            zoom = "1.06"
            fraction = f"on/{max(length, 1)}"
            x = f"(iw-iw/zoom)*({fraction})" if motion == "pan-right" else f"(iw-iw/zoom)*(1-{fraction})"
        text.append(f"zoompan=z='{zoom}':x='{x}':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}")
    size = max(22, round(w * 0.047))
    subtitle = max(18, round(w * 0.024))
    text.append(f"drawtext=fontfile='{ff_filter_path(font)}':textfile='{ff_filter_path(title)}':"
                f"fontsize={size}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:"
                f"box=1:boxcolor=black@0.52:boxborderw={max(6,w//120)}")
    if scene.get("subtitle"):
        sub = tempdir / f"subtitle-{index:03d}.txt"
        sub.write_text(scene["subtitle"], encoding="utf-8")
        text.append(f"drawtext=fontfile='{ff_filter_path(font)}':textfile='{ff_filter_path(sub)}':"
                    f"fontsize={subtitle}:fontcolor=0x{scene['accent'][1:]}:"
                    f"x=(w-text_w)/2:y=h*0.68")
    fade = min(.35, scene["duration"] / 5)
    text.append(f"fade=t=in:st=0:d={fade:.3f}")
    text.append(f"fade=t=out:st={scene['duration'] - fade:.3f}:d={fade:.3f}")
    text.append("format=yuv420p")
    return ",".join(text)


def run(command: list[str], timeout: float) -> None:
    # No shell, no remote URLs, no unreviewed model/provider process.
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise MotionError("FFmpeg rendering timed out") from exc
    except subprocess.CalledProcessError as exc:
        raise MotionError("FFmpeg failed: " + exc.stderr.decode("utf-8", "replace")[-700:]) from exc


def render(project_path: Path, output: Path, *, font: Path | None = None,
           crf: int = 18, preset: str = "medium", threads: int = 2,
           force: bool = False) -> dict:
    require(shutil.which("ffmpeg") is not None, "FFmpeg executable missing")
    require(type(crf) is int and 10 <= crf <= 30, "CRF must be 10-30")
    require(preset in {"ultrafast", "fast", "medium", "slow"}, "invalid H.264 preset")
    require(type(threads) is int and 1 <= threads <= 16, "threads must be 1-16")
    project_path = project_path.resolve(strict=True)
    story = load_project(project_path)
    output = output.absolute()
    require(output.suffix.lower() == ".mp4" and output.parent.is_dir()
            and not output.is_symlink() and (force or not output.exists()),
            "output must be a new local MP4 (or use --force)")
    require(not output.is_relative_to(project_path.parent / "assets"),
            "output cannot overwrite source assets")
    if font is None:
        font = next((Path(p) for p in FONT_CHOICES if Path(p).is_file()), None)
    require(font is not None and font.is_file(), "provide an installed font via --font")
    font = font.resolve(strict=True)
    require(font.suffix.lower() in {".ttf", ".otf"}, "font must be TTF or OTF")
    require(shutil.disk_usage(output.parent).free >= 100 * 1024 * 1024,
            "less than 100 MiB free on output volume")
    w, h, fps = story["width"], story["height"], story["fps"]
    total = sum(x["duration"] for x in story["scenes"])
    with tempfile.TemporaryDirectory(prefix="nexus-motion-", dir=output.parent) as directory:
        work = Path(directory)
        segments = []
        for n, scene in enumerate(story["scenes"]):
            target = work / f"scene-{n:03d}.mp4"
            if scene.get("image"):
                image = safe_media(project_path.parent, scene["image"], CODECS, 64*1024*1024)
                cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
                       "-loop", "1", "-framerate", str(fps),
                       "-protocol_whitelist", "file,pipe", "-i", str(image)]
            else:
                cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
                       "-f", "lavfi", "-i",
                       f"color=c=0x{scene['background'][1:]}:s={w}x{h}:r={fps}"]
            filt = scene_filter(scene, project_path.parent, work, n, w, h, fps, font)
            cmd += ["-t", str(scene["duration"]), "-vf", filt, "-an",
                    "-c:v", "libx264", "-threads", str(threads),
                    "-preset", preset, "-crf", str(crf),
                    "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(target)]
            run(cmd, max(180, scene["duration"] * 90))
            require(target.is_file() and target.stat().st_size > 500, "scene render is empty")
            segments.append(target)
        manifest = work / "parts.ffconcat"
        manifest.write_text("ffconcat version 1.0\n" +
                            "".join(f"file 'scene-{i:03d}.mp4'\n" for i in range(len(segments))),
                            encoding="utf-8")
        joined = work / "joined.mp4"
        run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
             "-safe", "0", "-f", "concat", "-protocol_whitelist", "file,pipe",
             "-i", str(manifest),
             "-c", "copy", "-movflags", "+faststart", str(joined)], max(180, total * 3))
        final = joined
        if story.get("soundtrack"):
            soundtrack = safe_media(project_path.parent, story["soundtrack"], AUDIO, 1024*1024*1024)
            final = work / "final.mp4"
            fade_at = max(0, total - 1.0)
            run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
                 "-protocol_whitelist", "file,pipe", "-i", str(joined),
                 "-protocol_whitelist", "file,pipe", "-i", str(soundtrack), "-map", "0:v:0",
                 "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                 "-af", f"apad,atrim=0:{total},afade=t=out:st={fade_at:.3f}:d=1",
                 "-t", str(total), "-movflags", "+faststart", str(final)], max(180, total * 3))
        require(final.is_file() and final.stat().st_size > 500, "render produced no MP4")
        os.replace(final, output)
    return {"status": "RENDERED_LOCAL_ONLY", "path": str(output), "bytes": output.stat().st_size,
            "width": w, "height": h, "fps": fps, "duration_seconds": total,
            "scenes": len(story["scenes"]), "soundtrack_attached": bool(story.get("soundtrack")),
            "ai_video_model_used": False, "upload_performed": False}


@contextmanager
def project_source(path: Path):
    """Accept either a JSON storyboard or the exact local STORE ZIP bundle.

    ZIP extraction is bounded, restricted to assets/ and storyboard.json,
    rejects duplicates/symlinks, and uses a temporary private directory.
    """
    if path.suffix.lower() != ".zip":
        require(path.suffix.lower() == ".json", "project must be .json or local .zip")
        yield path
        return
    require(path.is_file() and not path.is_symlink()
            and 0 < path.stat().st_size <= 100 * 1024 * 1024,
            "invalid or oversized project ZIP")
    with tempfile.TemporaryDirectory(prefix="nexus-motion-input-") as folder:
        target = Path(folder)
        try:
            with zipfile.ZipFile(path, "r", allowZip64=False) as archive:
                entries = archive.infolist()
                require(1 <= len(entries) <= 123, "ZIP contains too many entries")
                require(sum(i.file_size for i in entries) <= 96 * 1024 * 1024,
                        "ZIP uncompressed media budget exceeded")
                seen = set()
                for info in entries:
                    name = info.filename
                    require(name not in seen, "duplicate ZIP filename")
                    seen.add(name)
                    mode = (info.external_attr >> 16) & 0o170000
                    require(not info.is_dir() and mode != 0o120000
                            and info.compress_type == zipfile.ZIP_STORED,
                            "links and compressed ZIP records are not allowed")
                    require(name == "storyboard.json"
                            or (name.startswith("assets/")
                                and FILES.fullmatch(name) is not None
                                and name.count("/") == 1
                                and Path(name).suffix.lower() in CODECS | AUDIO),
                            "unexpected ZIP path")
                    require(info.file_size <= (1024*1024*1024 if name.endswith(".wav") else 64*1024*1024),
                            "ZIP entry too large")
                    dest = target / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as src, dest.open("xb") as out:
                        shutil.copyfileobj(src, out, 128 * 1024)
                    require(dest.stat().st_size == info.file_size, "ZIP truncated entry")
                require("storyboard.json" in seen, "ZIP missing storyboard.json")
        except (zipfile.BadZipFile, EOFError) as exc:
            raise MotionError("invalid ZIP container") from exc
        yield target / "storyboard.json"


def main() -> int:
    p = argparse.ArgumentParser(description="NEXUS Motion: local scene-by-scene MP4 renderer")
    p.add_argument("storyboard", type=Path, help="Project JSON next to local assets/")
    p.add_argument("output", type=Path, help="New .mp4 output filename")
    p.add_argument("--font", type=Path, default=None)
    p.add_argument("--crf", type=int, default=18, help="Quality: 10 highest, 30 lower; default 18")
    p.add_argument("--preset", choices=["ultrafast", "fast", "medium", "slow"], default="medium")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--force", action="store_true")
    p.add_argument("--check", action="store_true", help="Validate project, no rendering")
    x = p.parse_args()
    try:
        with project_source(x.storyboard) as project:
            if x.check:
                story = load_project(project)
                report = {"status": "VALID_LOCAL_PROJECT", "scenes": len(story["scenes"]),
                          "duration_seconds": sum(q["duration"] for q in story["scenes"]),
                          "width": story["width"], "height": story["height"], "fps": story["fps"]}
            else:
                report = render(project, x.output, font=x.font, crf=x.crf,
                                preset=x.preset, threads=x.threads, force=x.force)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (MotionError, OSError, FileNotFoundError) as exc:
        print("NEXUS MOTION: DENIED (" + str(exc) + ")", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
