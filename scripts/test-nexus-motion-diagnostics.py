#!/usr/bin/env python3
"""Real bounded visual FFmpeg diagnostics and 4K disk-admission planning tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def load(filename: str, name: str):
    spec=importlib.util.spec_from_file_location(name, ROOT/"scripts"/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D=load("nexus-motion-diagnostics.py", "nexus_motion_visual_diagnostics_tests")
R=load("nexus-motion-resume.py", "nexus_motion_resume_visual_tests")
T=load("test-nexus-motion-render.py", "nexus_motion_real_fixture_tests")


class MotionDiagnosticsTests(unittest.TestCase):
    def test_plan_large_4k_is_advisory_not_false_guarantee(self):
        story=T.storyboard()
        story["width"],story["height"],story["fps"]=3840,2160,60
        for scene in story["scenes"]:
            scene["duration"]=900
        p=D.plan(story,free_disk_bytes=500*D.MIB)
        self.assertEqual(p["status"],"ADVISORY_ESTIMATE_ONLY")
        self.assertEqual(p["total_expected_frames"],108000)
        self.assertTrue(p["free_space_below_recommendation"])
        self.assertFalse(p["size_estimate_is_hard_upper_bound"])
        self.assertEqual(p["suggested_max_new_scenes_per_batch"],1)
        self.assertFalse(p["release_authorized"])

    def test_plan_clear_capacity_and_low_absolute_minimum(self):
        story=T.storyboard()
        roomy=D.plan(story,free_disk_bytes=500*D.GIB)
        self.assertFalse(roomy["free_space_below_recommendation"])
        self.assertEqual(roomy["recommended_action"],"CAPACITY_ESTIMATE_NOT_EXCEEDED")
        insufficient=D.plan(story,free_disk_bytes=64*D.MIB)
        self.assertTrue(insufficient["below_absolute_minimum_128mib"])
        self.assertEqual(insufficient["recommended_action"],"STOP_UNDER_ABSOLUTE_MINIMUM")

    def test_plan_refuses_malformed_or_unbounded_storyboard(self):
        for change in (
            {"width":9999},{"height":True},{"fps":120},{"fps":True},
            {"scenes":[]},{"scenes":[{"duration":900}]*121},
            {"scenes":[{"duration":True}]},
        ):
            with self.subTest(change=change),self.assertRaises(D.BASE.MotionError):
                D.plan({**T.storyboard(),**change},free_disk_bytes=500*D.GIB)
        with self.assertRaises(D.BASE.MotionError):
            D.plan(T.storyboard(),free_disk_bytes=-1)
        with self.assertRaises(D.BASE.MotionError):
            D.plan(T.storyboard(),free_disk_bytes=True)

    def test_sampling_stays_small_and_never_claims_full_coverage(self):
        self.assertEqual(D.sample_offsets(2),[0])
        self.assertEqual(D.sample_offsets(120),[0,59,118])
        self.assertEqual(D.sample_offsets(7200),[0,3599,7198])
        for value in (0,7201,True):
            with self.assertRaises(D.BASE.MotionError):
                D.sample_offsets(value)

    def test_visual_scan_rejects_symlink_and_empty_input(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bad=root/"bad.mp4"
            bad.write_bytes(b"")
            symlink=root/"linked.mp4"
            symlink.symlink_to(bad)
            for item in (bad,symlink):
                with self.assertRaises(D.BASE.MotionError):
                    D.scan_visual(item,duration=2)

    def test_real_ffmpeg_black_and_freeze_are_warning_not_denial(self):
        if not shutil.which("ffmpeg"):self.skipTest("FFmpeg required")
        with tempfile.TemporaryDirectory() as d:
            movie=Path(d)/"intentional-black.mp4"
            subprocess.run([
                "ffmpeg","-nostdin","-hide_banner","-v","error","-y",
                "-f","lavfi","-i","color=c=black:s=320x180:r=24",
                "-t","3","-an","-c:v","libx264","-threads","1",
                "-preset","ultrafast","-pix_fmt","yuv420p",str(movie),
            ],check=True,capture_output=True,timeout=35)
            report=D.scan_visual(movie,duration=3)
            self.assertEqual(report["status"],"ADVISORY_ONLY")
            self.assertTrue(report["review_suggested"])
            self.assertFalse(report["warning_is_render_failure"])
            self.assertFalse(report["entire_video_scanned"])
            self.assertFalse(report["color_motion_parity_verified"])
            self.assertFalse(report["artistic_quality_assessed"])
            self.assertFalse(report["release_authorized"])
            self.assertGreaterEqual(len(report["sampling_windows"]),1)

    def test_technical_qc_and_visual_advisory_can_coexist_in_real_mp4(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg/ffprobe required")
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            project=T.prepare(folder)
            output=folder/"real.mp4"
            result=R.render(project,output,crf=28,preset="ultrafast",
                            threads=2,visual_qc=True)
            self.assertTrue(result["technical_mp4_verified"])
            self.assertTrue(result["visual_qc_performed"])
            report_file=Path(result["visual_report"])
            self.assertTrue(report_file.is_file())
            report=json.loads(report_file.read_text(encoding="utf-8"))
            self.assertEqual(report["status"],"ADVISORY_ONLY")
            self.assertFalse(report["release_authorized"])
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size,1000)

    def test_missing_advisory_does_not_block_default_renderer(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg/ffprobe required")
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            project=T.prepare(folder)
            output=folder/"plain.mp4"
            result=R.render(project,output,crf=28,preset="ultrafast",threads=2)
            self.assertFalse(result["visual_qc_performed"])
            self.assertIsNone(result["visual_report"])
            self.assertTrue(output.is_file())

    def test_failed_requested_visual_scan_preserves_existing_output(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg/ffprobe required")
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            project=T.prepare(folder)
            output=folder/"protected.mp4"
            output.write_bytes(b"original-user-data")
            with patch.object(R.DIAG,"scan_visual",side_effect=R.BASE.MotionError("forced visual scan failure")):
                with self.assertRaisesRegex(R.BASE.MotionError,"forced visual"):
                    R.render(project,output,force=True,crf=28,
                             preset="ultrafast",threads=2,visual_qc=True)
            self.assertEqual(output.read_bytes(),b"original-user-data")

    def test_no_external_inference_or_auto_upload(self):
        source=(ROOT/"scripts/nexus-motion-diagnostics.py").read_text(encoding="utf-8")
        for bad in ("subprocess.Popen(","shell=True","requests.post(",
                    "urllib.request","os.system(","http://","https://"):
            self.assertNotIn(bad,source)


if __name__=="__main__":
    unittest.main(verbosity=2)
