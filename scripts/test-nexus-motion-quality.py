#!/usr/bin/env python3
"""Real FFmpeg/ffprobe checks of NEXUS Motion's bounded technical QC report."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

QC = load("nexus-motion-quality.py", "nexus_motion_quality")
T = load("test-nexus-motion-render.py", "nexus_motion_render_testlib")
RENDER = load("nexus-motion-render.py", "nexus_motion_native_testlib")
RESUME = load("nexus-motion-resume.py", "nexus_motion_resume_testlib")


class TechnicalQualityTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Native ffmpeg and ffprobe required")
        folder = tempfile.TemporaryDirectory(prefix="nexus-qc-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.project = T.prepare(self.root)

    def real_movie(self):
        movie = self.root / "example.mp4"
        RENDER.render(self.project, movie, crf=28, preset="ultrafast", threads=2)
        return movie

    def test_real_h264_aac_720p_exact_frame_packets(self):
        movie = self.real_movie()
        result = QC.check(movie, width=1280, height=720,
                          fps=24, duration=2, require_audio=True)
        self.assertEqual(result["status"], "TECHNICAL_MP4_VERIFIED")
        self.assertEqual(result["expected_frames"], 48)
        self.assertEqual(result["verified_video_packets"], 48)
        self.assertEqual(result["audio"]["codec"], "aac")
        self.assertEqual(result["sha256"], QC.sha256(movie))
        self.assertFalse(result["full_video_decode_performed"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["upload_performed"])

    def test_bad_expected_fps_dimensions_duration_audio_denied(self):
        movie = self.real_movie()
        defaults = dict(width=1280, height=720, fps=24, duration=2, require_audio=True)
        for key, wrong in [("width",1920),("height",1080),("fps",30),
                           ("duration",1),("require_audio",False)]:
            with self.subTest(key=key), self.assertRaises(QC.QualityError):
                case = dict(defaults)
                case[key] = wrong
                QC.check(movie, **case)

    def test_empty_and_linked_video_file_denied(self):
        empty = self.root / "empty.mp4"
        empty.write_bytes(b"")
        linked = self.root / "alias.mp4"
        linked.symlink_to(empty)
        for item in (empty, linked):
            with self.assertRaises(QC.QualityError):
                QC.check(item, width=1280, height=720, fps=24,
                         duration=2, require_audio=True)

    def test_no_audio_is_accepted_only_when_expected(self):
        movie = self.root / "no-audio.mp4"
        story = T.storyboard()
        story.pop("soundtrack")
        self.project.write_text(json.dumps(story))
        RENDER.render(self.project, movie, crf=28, preset="ultrafast", threads=2)
        report = QC.check(movie, width=1280, height=720, fps=24,
                          duration=2, require_audio=False)
        self.assertIsNone(report["audio"])
        with self.assertRaises(QC.QualityError):
            QC.check(movie, width=1280, height=720, fps=24,
                     duration=2, require_audio=True)

    def test_single_real_4k_h264_frame_smoke(self):
        # Only confirms a real 4K H.264 encoding path. This is NOT a 4K
        # throughput, long video, HDR, or Android thermal acceptance test.
        frame = self.root / "4k-one-frame.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-v", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=0x182238:s=3840x2160:r=24",
            "-frames:v", "1", "-an", "-c:v", "libx264", "-threads", "2",
            "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p",
            str(frame)
        ], check=True, capture_output=True, timeout=90)
        data = QC.get_probe(frame)
        video = next(s for s in data["streams"] if s["codec_type"] == "video")
        self.assertEqual((video["width"], video["height"]), (3840,2160))
        self.assertEqual(video["codec_name"], "h264")
        self.assertEqual(int(video["nb_read_packets"]), 1)

    def test_manifest_quality_report_matches_actual_final_output(self):
        out = self.root / "resume.mp4"
        result = RESUME.render(self.project, out, crf=28,
                               preset="ultrafast", threads=2)
        self.assertTrue(result["technical_mp4_verified"])
        report_file = Path(result["quality_report"])
        self.assertTrue(report_file.is_file())
        report = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertEqual(report["sha256"], QC.sha256(out))
        self.assertEqual(report["verified_video_packets"], 48)
        self.assertEqual(report["expected_frames"], 48)

    def test_malformed_packet_count_denied(self):
        for value in (None, 0, 1, True, "-1", "001", "10.0", " 1", "NaN"):
            with self.subTest(value=value), self.assertRaises(QC.QualityError):
                QC.integer_text(value)
        self.assertEqual(QC.integer_text("48"),48)

    def test_nonfinite_timestamps_and_invalid_frame_rates_denied(self):
        for value in ("nan","inf","-inf",None):
            with self.subTest(value=value), self.assertRaises(QC.QualityError):
                QC.seconds(value)
        for value in ("25/0","bad","4","0/0",None):
            with self.subTest(value=value), self.assertRaises(QC.QualityError):
                QC.fraction(value)

    def test_no_cloud_integration_or_publication(self):
        code = (ROOT/"scripts/nexus-motion-quality.py").read_text(encoding="utf-8")
        for fragment in ("subprocess.Popen(", "shell=True", "urllib.request",
                         "requests.post(", "gh release", "os.system("):
            self.assertNotIn(fragment, code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
