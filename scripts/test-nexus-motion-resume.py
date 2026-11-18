#!/usr/bin/env python3
"""Adversarial and actual FFmpeg resume acceptance, with no cloud or GPU."""
from __future__ import annotations
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def imported(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

Q = imported("nexus-motion-resume.py", "nexus_motion_resume")
T = imported("test-nexus-motion-render.py", "nexus_motion_render_tests")


class ResumeTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Real FFmpeg/ffprobe required")
        self.temp = tempfile.TemporaryDirectory(prefix="nexus-motion-resume-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = T.prepare(self.root)
        self.out = self.root / "movie.mp4"

    def render(self, **options):
        settings = {"preset": "ultrafast", "crf": 28, "threads": 2}
        settings.update(options)
        return Q.render(self.project, self.out, **settings)

    def test_real_interrupt_resume_reuse_and_final_audio(self):
        first = self.render(max_new_scenes=1)
        self.assertEqual(first["status"], "PAUSED_RESUMABLE")
        self.assertEqual(first["rendered_scenes"], 1)
        self.assertFalse(self.out.exists())
        cache = self.out.with_name(self.out.name + ".motion-work")
        original = cache / "scene-000.mp4"
        old_digest = Q.digest(original)
        second = self.render(resume=True, max_new_scenes=1)
        self.assertEqual(second["status"], "RENDERED_RESUMABLE_LOCAL")
        self.assertEqual(second["reused_scenes"], 1)
        self.assertEqual(second["rendered_scenes"], 1)
        self.assertEqual(Q.digest(original), old_digest)
        self.assertTrue(self.out.exists())
        Q.verify_video(self.out, w=1280, h=720, fps=24, seconds=2, audio=True)
        self.assertFalse(second["upload_performed"])

    def test_tampered_cached_mp4_is_rendered_again(self):
        first = self.render(max_new_scenes=1)
        cache = Path(first["workspace"])
        segment = cache / "scene-000.mp4"
        segment.write_bytes(b"forged stream with mismatched digest")
        result = self.render(resume=True)
        self.assertEqual(result["rendered_scenes"], 2)
        self.assertEqual(result["reused_scenes"], 0)
        self.assertTrue(segment.stat().st_size > 500)

    def test_changed_original_media_or_profile_is_not_reused(self):
        first = self.render(max_new_scenes=1)
        with self.assertRaisesRegex(Q.BASE.MotionError, "profile"):
            self.render(resume=True, crf=19)
        with self.assertRaisesRegex(Q.BASE.MotionError, "profile"):
            self.render(resume=True, threads=3)
        with (self.root / "assets/sound.wav").open("ab") as stream:
            stream.write(b"source-modified")
        with self.assertRaisesRegex(Q.BASE.MotionError, "profile"):
            self.render(resume=True)
        self.assertFalse(self.out.exists())
        self.assertTrue(Path(first["workspace"]).exists())

    def test_corrupted_checkpoint_does_not_authorize_render(self):
        first = self.render(max_new_scenes=1)
        cache = Path(first["workspace"])
        (cache / "manifest.json").write_text('{"schema":"x","schema":"y"}',encoding="utf-8")
        with self.assertRaises(Q.BASE.MotionError):
            self.render(resume=True)

    def test_symlink_segment_and_unrecognized_cache_files_denied(self):
        first = self.render(max_new_scenes=1)
        cache = Path(first["workspace"])
        segment = cache / "scene-000.mp4"
        segment.unlink()
        segment.symlink_to(self.project)
        with self.assertRaisesRegex(Q.BASE.MotionError, "linked"):
            self.render(resume=True)
        segment.unlink()
        (cache / "user-file.secret").write_text("must never be read/deleted")
        with self.assertRaisesRegex(Q.BASE.MotionError, "unrecognized"):
            self.render(resume=True)

    def test_concurrent_job_is_denied(self):
        first = self.render(max_new_scenes=1)
        cache = Path(first["workspace"])
        with Q.exclusive(cache):
            with self.assertRaisesRegex(Q.BASE.MotionError, "owns this job"):
                with Q.exclusive(cache):
                    pass

    def test_resume_refuses_missing_job(self):
        with self.assertRaisesRegex(Q.BASE.MotionError, "workspace"):
            self.render(resume=True)

    def test_old_published_output_not_overwritten_by_failed_resume(self):
        first = self.render(max_new_scenes=1)
        self.out.write_bytes(b"original-user-output")
        with self.assertRaises(Q.BASE.MotionError):
            self.render(resume=True)
        self.assertEqual(self.out.read_bytes(), b"original-user-output")
        # Explicit replacement must still never happen if source profile changed.
        s = json.loads(self.project.read_text(encoding="utf-8"))
        s["title"] = "changed storyboard"
        self.project.write_text(json.dumps(s))
        with self.assertRaises(Q.BASE.MotionError):
            self.render(resume=True, force=True)
        self.assertEqual(self.out.read_bytes(), b"original-user-output")

    def test_resumption_from_browser_store_zip_after_reextraction(self):
        archive = self.root / "original.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
            for item in (self.project, self.root/"assets/photo.png",
                         self.root/"assets/sound.wav"):
                z.write(item, item.relative_to(self.root).as_posix())
        with Q.BASE.project_source(archive) as extracted:
            result = Q.render(extracted, self.out, max_new_scenes=1,
                              crf=28, preset="ultrafast", threads=2)
            self.assertEqual(result["status"], "PAUSED_RESUMABLE")
        with Q.BASE.project_source(archive) as extracted:
            result = Q.render(extracted, self.out, resume=True,
                              crf=28, preset="ultrafast", threads=2)
            self.assertEqual(result["reused_scenes"], 1)
        self.assertTrue(self.out.exists())

    def test_recover_after_output_exists_with_explicit_force(self):
        self.render(max_new_scenes=1)
        self.render(resume=True)
        data = self.out.read_bytes()
        result = self.render(resume=True, force=True)
        self.assertEqual(result["reused_scenes"], 2)
        self.assertEqual(result["rendered_scenes"], 0)
        self.assertEqual(self.out.read_bytes(), data)

    def test_no_external_host_or_automatic_scheduling(self):
        source = (ROOT / "scripts/nexus-motion-resume.py").read_text()
        for forbidden in ("shell=True", "requests.", "urllib.request",
                          "http://", "https://", "os.system(", "subprocess.Popen("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
