#!/usr/bin/env python3
"""Actual scene-boundary video-frame continuity acceptance; warning-only semantics."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    out = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(out)
    return out


S = module("nexus-motion-seams.py", "nexus_motion_seam_test")
R = module("nexus-motion-resume.py", "nexus_motion_resume_seam_test")
T = module("test-nexus-motion-render.py", "nexus_motion_fixture_seam_test")


def story():
    result = T.storyboard()
    result.pop("soundtrack", None)
    result["scenes"][0]["title"] = "FIRST"
    result["scenes"][1]["title"] = "SECOND"
    return result


class SeamContractTests(unittest.TestCase):
    def test_sampling_never_exceeds_24_even_with_120_scenes(self):
        indices = S.sample_indices(120)
        self.assertEqual(len(indices), 24)
        self.assertEqual(indices[0], 1)
        self.assertEqual(indices[-1], 119)
        self.assertEqual(len(set(indices)), 24)
        self.assertEqual(S.sample_indices(1), [])
        self.assertEqual(S.sample_indices(3), [1, 2])
        self.assertEqual(S.sample_indices(120, limit=1), [1])

    def test_invalid_scene_limits_are_denied(self):
        for count in (0, 121, True, "2"):
            with self.subTest(count=count), self.assertRaises(S.base.MotionError):
                S.sample_indices(count)
        for limit in (0, 25, True, 2.5):
            with self.subTest(limit=limit), self.assertRaises(S.base.MotionError):
                S.sample_indices(3, limit=limit)

    def test_luma_mae_exact_and_malformed_frames_denied(self):
        dark = bytes([0]) * S.FRAME_BYTES
        light = bytes([255]) * S.FRAME_BYTES
        self.assertEqual(S.average_luminance_difference(dark, dark), 0.0)
        self.assertEqual(S.average_luminance_difference(dark, light), 1.0)
        with self.assertRaises(S.base.MotionError):
            S.average_luminance_difference(dark, b"short")


class RealSeamTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Native FFmpeg/ffprobe required")
        self.temp = tempfile.TemporaryDirectory(prefix="nexus-seam-real-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_two_color_mp4(self, second_color="white"):
        movie = self.root / f"two-scene-{second_color}.mp4"
        p = subprocess.run([
            "ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1",
            "-f", "lavfi", "-i", f"color=c={second_color}:s=320x180:r=24:d=1",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p",
            "-an", "-c:v", "libx264", "-threads", "2",
            "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(movie),
        ], capture_output=True, check=True, timeout=50)
        self.assertGreater(movie.stat().st_size, 500)
        return movie

    def test_actual_abrupt_black_white_boundary_is_flagged(self):
        movie = self.make_two_color_mp4("white")
        report = S.scan(movie, story())
        self.assertEqual(report["status"], "ADVISORY_ONLY")
        self.assertEqual(report["sampled_boundaries"], 1)
        self.assertEqual(report["total_scene_boundaries"], 1)
        self.assertTrue(report["review_suggested"])
        self.assertGreater(report["seams"][0]["luma_mae"], 0.8)
        self.assertEqual(report["seams"][0]["preceding_frame_index"], 23)
        self.assertEqual(report["seams"][0]["following_frame_index"], 24)
        self.assertFalse(report["render_failure"])
        self.assertFalse(report["pixel_parity_with_canvas_proven"])

    def test_identical_black_scenes_do_not_false_flag(self):
        movie = self.make_two_color_mp4("black")
        report = S.scan(movie, story())
        self.assertFalse(report["review_suggested"])
        self.assertLess(report["seams"][0]["luma_mae"], .01)

    def test_real_resumable_render_writes_optional_seam_report(self):
        project = T.prepare(self.root)
        movie = self.root / "rendered.mp4"
        report = R.render(project, movie, crf=28, preset="ultrafast",
                          threads=2, seam_qc=True)
        self.assertEqual(report["status"], "RENDERED_RESUMABLE_LOCAL")
        self.assertTrue(report["technical_mp4_verified"])
        self.assertTrue(report["seam_qc_performed"])
        seam_file = Path(report["seam_report"])
        self.assertTrue(seam_file.is_file())
        data = json.loads(seam_file.read_text(encoding="utf-8"))
        self.assertEqual(data["sampled_boundaries"], 1)
        self.assertFalse(data["release_authorized"])
        self.assertFalse(data["full_video_quality_assessed"])
        self.assertTrue(movie.is_file())

    def test_default_render_does_not_claim_seam_analysis(self):
        project = T.prepare(self.root)
        movie = self.root / "default.mp4"
        report = R.render(project, movie, crf=28, preset="ultrafast",
                          threads=2)
        self.assertFalse(report["seam_qc_performed"])
        self.assertIsNone(report["seam_report"])

    def test_failed_requested_seam_scan_does_not_replace_existing_mp4(self):
        project = T.prepare(self.root)
        movie = self.root / "protected.mp4"
        movie.write_bytes(b"original-user-bytes")
        with patch.object(R.SEAM, "scan", side_effect=R.BASE.MotionError("forced decoder error")):
            with self.assertRaisesRegex(R.BASE.MotionError, "forced decoder"):
                R.render(project, movie, crf=28, preset="ultrafast",
                         threads=2, force=True, seam_qc=True)
        self.assertEqual(movie.read_bytes(), b"original-user-bytes")

    def test_symlink_and_malformed_timeline_denied(self):
        movie = self.make_two_color_mp4()
        linked = self.root / "linked.mp4"
        linked.symlink_to(movie)
        with self.assertRaises(S.base.MotionError):
            S.scan(linked, story())
        for unexpected in (True, 0, 120, "24"):
            sample = story()
            sample["fps"] = unexpected
            with self.subTest(fps=unexpected), self.assertRaises(S.base.MotionError):
                S.scan(movie, sample)

    def test_no_network_or_publish_code(self):
        source = (ROOT / "scripts/nexus-motion-seams.py").read_text()
        for forbidden in ("shell=True", "requests.post(", "urllib.request",
                          "os.system(", "gh release", "subprocess.Popen("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
