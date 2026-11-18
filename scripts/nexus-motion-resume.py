#!/usr/bin/env python3
"""NEXUS Motion: resumable local H.264 scene queue, no background runner or network.

A scene is reusable only when its SHA-256, exact profile fingerprint AND
ffprobe stream properties are verified. Interrupted output never replaces the
published MP4. Linux/Android Termux flock prevents concurrent writers.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("nexus_motion_base", ROOT / "nexus-motion-render.py")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
QC_SPEC = importlib.util.spec_from_file_location("nexus_motion_quality", ROOT / "nexus-motion-quality.py")
QUALITY = importlib.util.module_from_spec(QC_SPEC)
QC_SPEC.loader.exec_module(QUALITY)
DIAG_SPEC = importlib.util.spec_from_file_location("nexus_motion_diagnostics", ROOT / "nexus-motion-diagnostics.py")
DIAG = importlib.util.module_from_spec(DIAG_SPEC)
DIAG_SPEC.loader.exec_module(DIAG)
SEAM_SPEC = importlib.util.spec_from_file_location("nexus_motion_seams", ROOT / "nexus-motion-seams.py")
SEAM = importlib.util.module_from_spec(SEAM_SPEC)
SEAM_SPEC.loader.exec_module(SEAM)
SCHEMA = "nexus.motion.resume.v1"
MIN_FREE = 128 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    BASE.require(condition, message)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(1024 * 1024):
            result.update(data)
    return result.hexdigest()


def probe(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size > 500,
            "missing, linked or empty video segment")
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            check=True, capture_output=True, timeout=25,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
        raise BASE.MotionError("video stream cannot be independently decoded by ffprobe") from exc


def verify_video(path: Path, *, w: int, h: int, fps: int, seconds: int, audio: bool) -> None:
    data = probe(path)
    streams = data.get("streams", [])
    require(type(streams) is list, "malformed probe streams")
    video = [s for s in streams if s.get("codec_type") == "video"]
    sound = [s for s in streams if s.get("codec_type") == "audio"]
    require(len(video) == 1 and video[0].get("codec_name") == "h264"
            and video[0].get("width") == w and video[0].get("height") == h,
            "cached scene has wrong H.264 identity or pixel dimensions")
    require((len(sound) == 1) == audio, "cached scene soundtrack mismatch")
    rate = video[0].get("avg_frame_rate", "0/0")
    try:
        num, den = map(int, rate.split("/"))
        duration = float(data["format"]["duration"])
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise BASE.MotionError("cached scene has missing timing evidence") from exc
    require(den > 0 and num == fps * den, "cached scene frame rate mismatch")
    require(abs(duration - seconds) <= max(.12, 2.0 / fps),
            "cached scene duration mismatch")


def identity(story: dict, project: Path, *, font: Path, crf: int,
             preset: str, threads: int) -> str:
    inputs = {}
    for scene in story["scenes"]:
        if scene.get("image"):
            asset = scene["image"]
            inputs[asset] = digest(BASE.safe_media(project.parent, asset, BASE.CODECS, 64*1024*1024))
    if story.get("soundtrack"):
        name = story["soundtrack"]
        inputs[name] = digest(BASE.safe_media(project.parent, name, BASE.AUDIO, 1024*1024*1024))
    try:
        version = subprocess.run(["ffmpeg", "-version"], check=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 timeout=15).stdout.splitlines()[0].decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError) as exc:
        raise BASE.MotionError("FFmpeg version could not be confirmed") from exc
    obj = {"schema": SCHEMA, "story": story, "media_sha256": inputs,
           "renderer_sha256": digest(ROOT / "nexus-motion-render.py"),
           "queue_sha256": digest(Path(__file__)),
           "quality_sha256": digest(ROOT / "nexus-motion-quality.py"),
           "diagnostics_sha256": digest(ROOT / "nexus-motion-diagnostics.py"),
           "seam_audit_sha256": digest(ROOT / "nexus-motion-seams.py"),
           "font_sha256": digest(font),
           "ffmpeg": version, "crf": crf, "preset": preset, "threads": threads}
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def safe_workspace(output: Path, *, resume: bool) -> Path:
    work = output.with_name(output.name + ".motion-work")
    require(not work.is_symlink(), "render workspace symlink denied")
    if work.exists():
        require(resume and work.is_dir(), "workspace exists; use --resume or choose a new output")
        require(work.stat().st_uid == os.getuid()
                and not (stat.S_IMODE(work.stat().st_mode) & 0o077),
                "render workspace must be privately owned with no group/world access")
    else:
        require(not resume, "no prior workspace exists to resume")
        work.mkdir(mode=0o700)
    # Only exact generated filenames are admitted. No arbitrary user files
    # are read, followed or recursively deleted within a workspace.
    for child in work.iterdir():
        require(not child.is_symlink() and child.is_file()
                and (child.name in {"manifest.json", "manifest.pending", ".lock",
                                    "joined.partial.mp4", "final.partial.mp4", "parts.ffconcat",
                                    "quality.json", "quality.pending",
                                    "visual.json", "visual.pending", "seams.json", "seams.pending"}
                     or (child.name.startswith("scene-") and
                         child.name[6:9].isdigit() and child.name[9:] in (".mp4", ".partial.mp4"))
                     or (child.name.startswith(("title-", "subtitle-")) and
                         child.name[-4:] == ".txt" and child.name[-7:-4].isdigit())),
                "unrecognized or linked render workspace file")
    return work


@contextmanager
def exclusive(work: Path):
    lock = work / ".lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and info.st_uid == os.getuid()
                and not (stat.S_IMODE(info.st_mode) & 0o077),
                "unsafe lock file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BASE.MotionError("a renderer already owns this job") from exc
        yield
    finally:
        os.close(fd)


def load_manifest(work: Path, fingerprint: str, *, resume: bool) -> dict:
    path = work / "manifest.json"
    if not path.exists():
        require(not resume, "resume manifest is missing; refusing ambiguous work")
        return {"schema": SCHEMA, "fingerprint": fingerprint, "segments": {}}
    require(resume and path.is_file() and not path.is_symlink()
            and path.stat().st_size <= 256_000, "invalid or unexpected resume manifest")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=BASE.pairs_unique)
    except (ValueError, UnicodeError) as exc:
        raise BASE.MotionError("corrupt or ambiguous resume manifest") from exc
    require(type(data) is dict and set(data) == {"schema", "fingerprint", "segments"}
            and data["schema"] == SCHEMA and data["fingerprint"] == fingerprint
            and type(data["segments"]) is dict, "cached render profile or input assets changed")
    return data


def save_manifest(work: Path, data: dict) -> None:
    target = work / "manifest.pending"
    require(not target.is_symlink(), "unsafe checkpoint")
    raw = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    require(len(raw) < 256_000, "checkpoint too large")
    with target.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(target, work / "manifest.json")
    directory = os.open(work, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def ensure_capacity(output: Path) -> None:
    require(shutil.disk_usage(output.parent).free >= MIN_FREE,
            "not enough free disk for safe continuation (minimum 128 MiB)")


def encode_scene(story: dict, project: Path, work: Path, index: int,
                 font: Path, *, crf: int, preset: str, threads: int) -> Path:
    scene = story["scenes"][index]
    w, h, fps = story["width"], story["height"], story["fps"]
    target = work / f"scene-{index:03d}.mp4"
    partial = work / f"scene-{index:03d}.partial.mp4"
    require(not partial.is_symlink() and not target.is_symlink(), "unsafe output scene")
    partial.unlink(missing_ok=True)
    if scene.get("image"):
        source = BASE.safe_media(project.parent, scene["image"], BASE.CODECS, 64*1024*1024)
        command = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
                   "-loop", "1", "-framerate", str(fps),
                   "-protocol_whitelist", "file,pipe", "-i", str(source)]
    else:
        command = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
                   "-f", "lavfi", "-i",
                   f"color=c=0x{scene['background'][1:]}:s={w}x{h}:r={fps}"]
    filtergraph = BASE.scene_filter(scene, project.parent, work, index, w, h, fps, font)
    command += ["-t", str(scene["duration"]), "-vf", filtergraph,
                "-an", "-c:v", "libx264", "-threads", str(threads),
                "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-r", str(fps), "-movflags", "+faststart", str(partial)]
    BASE.run(command, max(180, scene["duration"] * 90))
    verify_video(partial, w=w, h=h, fps=fps, seconds=scene["duration"], audio=False)
    os.replace(partial, target)
    return target


def create_output(story: dict, project: Path, output: Path, work: Path, *,
                  visual_qc: bool = False, seam_qc: bool = False) -> dict:
    count = len(story["scenes"])
    total = sum(scene["duration"] for scene in story["scenes"])
    w, h, fps = story["width"], story["height"], story["fps"]
    joinfile = work / "parts.ffconcat"
    joinfile.write_text("ffconcat version 1.0\n" +
                        "".join(f"file 'scene-{index:03d}.mp4'\n" for index in range(count)),
                        encoding="utf-8")
    joined = work / "joined.partial.mp4"
    joined.unlink(missing_ok=True)
    BASE.run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
              "-safe", "0", "-f", "concat", "-protocol_whitelist", "file,pipe",
              "-i", str(joinfile), "-c", "copy", "-movflags", "+faststart", str(joined)],
             max(180, total * 3))
    final = joined
    if story.get("soundtrack"):
        music = BASE.safe_media(project.parent, story["soundtrack"], BASE.AUDIO, 1024*1024*1024)
        final = work / "final.partial.mp4"
        final.unlink(missing_ok=True)
        BASE.run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
                  "-protocol_whitelist", "file,pipe", "-i", str(joined),
                  "-protocol_whitelist", "file,pipe", "-i", str(music),
                  "-map", "0:v:0", "-map", "1:a:0",
                  "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                  "-af", f"apad,atrim=0:{total},afade=t=out:st={max(0,total-1):.3f}:d=1",
                  "-t", str(total), "-movflags", "+faststart", str(final)],
                 max(180, total * 3))
    verify_video(final, w=w, h=h, fps=fps, seconds=total,
                 audio=bool(story.get("soundtrack")))
    # Packet/timebase audit is a separate, stricter technical gate than
    # the scene-level header check. The final MP4 is NOT published if this fails.
    report = QUALITY.check(final, width=w, height=h, fps=fps, duration=total,
                           require_audio=bool(story.get("soundtrack")))
    checkpoint = work / "quality.pending"
    require(not checkpoint.is_symlink(), "unsafe quality checkpoint")
    with checkpoint.open("wb") as handle:
        handle.write((json.dumps(report, sort_keys=True) + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(checkpoint, work / "quality.json")
    visual = None
    if visual_qc:
        # Bounded sampled visual warnings are advisory, unlike the mandatory
        # packet/audio quality gate. Scene fades and stills can trigger alerts.
        visual = DIAG.scan_visual(final, duration=total)
        visual_checkpoint = work / "visual.pending"
        require(not visual_checkpoint.is_symlink(), "unsafe visual report checkpoint")
        with visual_checkpoint.open("wb") as handle:
            handle.write((json.dumps(visual, sort_keys=True) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(visual_checkpoint, work / "visual.json")
    seams = None
    if seam_qc:
        seams = SEAM.scan(final, story)
        checkpoint = work / "seams.pending"
        require(not checkpoint.is_symlink(), "unsafe seam checkpoint")
        with checkpoint.open("wb") as handle:
            handle.write((json.dumps(seams, sort_keys=True) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(checkpoint, work / "seams.json")
    require(not output.is_symlink(), "final output became a symlink")
    os.replace(final, output)
    return {"seam_qc_performed": seams is not None,
            "seam_review_suggested": bool(seams and seams["review_suggested"]),
            "seam_report": str(work / "seams.json") if seams is not None else None,
            "visual_qc_performed": visual is not None,
            "visual_review_suggested": bool(visual and visual["review_suggested"]),
            "visual_report": str(work / "visual.json") if visual is not None else None}


def render(project: Path, output: Path, *, resume: bool = False,
           force: bool = False, font: Path | None = None, crf: int = 18,
           preset: str = "medium", threads: int = 2, max_new_scenes: int | None = None,
           visual_qc: bool = False, seam_qc: bool = False) -> dict:
    require(shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None,
            "FFmpeg and ffprobe must be installed")
    require(type(crf) is int and 10 <= crf <= 30, "CRF out of range")
    require(preset in {"ultrafast", "fast", "medium", "slow"}, "preset unsupported")
    require(type(threads) is int and 1 <= threads <= 16, "thread count unsupported")
    require(type(visual_qc) is bool and type(seam_qc) is bool,
            "scene diagnostic flags must be boolean")
    require(max_new_scenes is None or (type(max_new_scenes) is int and 1 <= max_new_scenes <= 120),
            "scene batch limit unsupported")
    output = output.absolute()
    require(output.suffix.lower() == ".mp4" and output.parent.is_dir()
            and not output.is_symlink() and (force or not output.exists()),
            "choose a new output filename (or --force to replace after verification)")
    require(not output.is_relative_to(project.parent.resolve(strict=True) / "assets"),
            "output may not replace a source media asset")
    if font is None:
        font = next((Path(name) for name in BASE.FONT_CHOICES if Path(name).is_file()), None)
    require(font is not None and font.is_file(), "font missing: pass --font local TTF/OTF")
    font = font.resolve(strict=True)
    require(font.suffix.lower() in {".ttf", ".otf"}, "invalid font type")
    story = BASE.load_project(project)
    ensure_capacity(output)
    fingerprint = identity(story, project, font=font, crf=crf, preset=preset, threads=threads)
    work = safe_workspace(output, resume=resume)
    with exclusive(work):
        state = load_manifest(work, fingerprint, resume=resume)
        if not resume:
            save_manifest(work, state)
        rendered = reused = 0
        for index, scene in enumerate(story["scenes"]):
            ensure_capacity(output)
            target = work / f"scene-{index:03d}.mp4"
            cached = state["segments"].get(str(index))
            okay = False
            if (type(cached) is dict and set(cached) == {"sha256", "size"}
                    and type(cached["size"]) is int and type(cached["sha256"]) is str
                    and not target.is_symlink() and target.is_file()
                    and target.stat().st_size == cached["size"]
                    and digest(target) == cached["sha256"]):
                try:
                    verify_video(target, w=story["width"], h=story["height"],
                                 fps=story["fps"], seconds=scene["duration"], audio=False)
                    okay = True
                except BASE.MotionError:
                    okay = False
            if okay:
                reused += 1
                continue
            if max_new_scenes is not None and rendered >= max_new_scenes:
                return {"status": "PAUSED_RESUMABLE", "rendered_scenes": rendered,
                        "reused_scenes": reused, "completed_scenes": index,
                        "total_scenes": len(story["scenes"]), "workspace": str(work),
                        "merge_authorized": False, "upload_performed": False}
            segment = encode_scene(story, project, work, index, font, crf=crf,
                                   preset=preset, threads=threads)
            state["segments"][str(index)] = {"sha256": digest(segment),
                                             "size": segment.stat().st_size}
            save_manifest(work, state)
            rendered += 1
        ensure_capacity(output)
        visual_report = create_output(story, project, output, work,
                                      visual_qc=visual_qc, seam_qc=seam_qc)
    return {"status": "RENDERED_RESUMABLE_LOCAL", "width": story["width"],
            "height": story["height"], "fps": story["fps"],
            "duration_seconds": sum(x["duration"] for x in story["scenes"]),
            "rendered_scenes": rendered, "reused_scenes": reused,
            "total_scenes": len(story["scenes"]), "bytes": output.stat().st_size,
            "path": str(output), "workspace": str(work),
            "ai_video_model_used": False, "upload_performed": False,
            "technical_mp4_verified": True, "quality_report": str(work / "quality.json"),
            **visual_report,
            "merge_authorized": False}


def main() -> int:
    p = argparse.ArgumentParser(description="NEXUS Motion: manually resumable offline MP4 scenes")
    p.add_argument("project", type=Path, help="JSON storyboard or browser-exported ZIP")
    p.add_argument("output", type=Path, help="MP4 file to create")
    p.add_argument("--resume", action="store_true", help="Resume an exact-bound cached job")
    p.add_argument("--force", action="store_true", help="Atomically replace an existing MP4")
    p.add_argument("--font", type=Path, default=None)
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--preset", choices=["ultrafast", "fast", "medium", "slow"], default="medium")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--max-new-scenes", type=int, default=None,
                   help="Thermal/battery-friendly bounded manual batch, then use --resume")
    p.add_argument("--visual-qc", action="store_true",
                   help="Scan three short windows for dark/frozen imagery (advisory only)")
    p.add_argument("--seam-qc", action="store_true",
                   help="Sample up to 24 scene boundary frame pairs (advisory only)")
    args = p.parse_args()
    try:
        with BASE.project_source(args.project) as project:
            report = render(project, args.output, resume=args.resume, force=args.force,
                            font=args.font, crf=args.crf, preset=args.preset,
                            threads=args.threads, max_new_scenes=args.max_new_scenes,
                            visual_qc=args.visual_qc, seam_qc=args.seam_qc)
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
        return 0
    except (BASE.MotionError, OSError, FileNotFoundError, ValueError) as error:
        print("NEXUS MOTION RESUME: DENIED (" + str(error) + ")", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
