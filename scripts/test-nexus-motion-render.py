#!/usr/bin/env python3
"""NEXUS Motion safety tests and real FFmpeg H.264/AAC acceptance (synthetic only)."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave
import math
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
script = ROOT / "scripts/nexus-motion-render.py"
spec = importlib.util.spec_from_file_location("nexus_motion_render", script)
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


def storyboard():
    return {
        "schema": render.SCHEMA,
        "title": "NEXUS MOTION TEST",
        "width": 1280, "height": 720, "fps": 24,
        "scenes": [
            {"duration": 1, "background": "#10203b", "accent": "#9de6d6",
             "title": "BEFORE THE LIGHT", "subtitle": "original synthetic title",
             "motion": "still"},
            {"duration": 1, "background": "#21324c", "accent": "#e2b787",
             "title": "AFTER THE LIGHT", "motion": "push", "image": "assets/photo.png"},
        ],
        "soundtrack": "assets/sound.wav",
    }


def prepare(root):
    media = root / "assets"
    media.mkdir()
    photo = media / "photo.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=1",
                    "-frames:v", "1", "-update", "1", str(photo)],
                   check=True, capture_output=True, timeout=25)
    sound = media / "sound.wav"
    with wave.open(str(sound), "wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(22050)
        frames=bytearray()
        for i in range(3*22050):
            frames.extend(struct.pack("<h", round(math.sin(i*2*math.pi*220/22050)*4000)))
        f.writeframes(frames)
    project = root / "storyboard.json"
    project.write_text(json.dumps(storyboard(),indent=2)+"\n",encoding="utf-8")
    return project


class MotionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix="nexus-motion-tests-")
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.project=prepare(self.root) if shutil.which("ffmpeg") else None

    def test_valid_native_storyboard(self):
        if not self.project:self.skipTest("FFmpeg is required")
        p=render.load_project(self.project)
        self.assertEqual(p["width"],1280)
        self.assertEqual(sum(s["duration"] for s in p["scenes"]),2)

    def deny(self, mutate):
        if not self.project:self.skipTest("FFmpeg is required")
        p=storyboard()
        mutate(p)
        with self.assertRaises(render.MotionError):
            render.validate(p,self.root)

    def test_cross_project_media_escape_denied(self):
        self.deny(lambda x:x["scenes"][1].update(image="../outside.jpg"))

    def test_url_is_not_accepted_as_media_path(self):
        self.deny(lambda x:x.update(soundtrack="https://evil.test/f.wav"))

    def test_unknown_keys_and_high_privilege_flags_denied(self):
        self.deny(lambda x:x.update(network=True))
        self.deny(lambda x:x["scenes"][0].update(shell="exec rm"))

    def test_length_and_resolution_limits(self):
        self.deny(lambda x:x.update(fps=120))
        self.deny(lambda x:x.update(width=16384,height=16384))
        self.deny(lambda x:x["scenes"][0].update(duration=901))
        self.deny(lambda x:x.update(scenes=x["scenes"]*61))

    def test_boolean_instead_of_duration_denied(self):
        self.deny(lambda x:x["scenes"][0].update(duration=True))

    def test_bad_color_and_motion_denied(self):
        self.deny(lambda x:x["scenes"][0].update(background="#red"))
        self.deny(lambda x:x["scenes"][0].update(motion="rotate;sh -c malware"))

    def test_banned_control_bytes_denied(self):
        self.deny(lambda x:x["scenes"][0].update(title="start\x00end"))

    def test_duplicate_json_properties_denied(self):
        if not self.project:self.skipTest("FFmpeg is required")
        self.project.write_text('{"schema":"a","schema":"b"}')
        with self.assertRaises(render.MotionError):
            render.load_project(self.project)

    def test_render_rejects_preexisting_output_without_force(self):
        if not self.project:self.skipTest("FFmpeg is required")
        out=self.root/"already.mp4"
        out.write_bytes(b"do-not-overwrite")
        with self.assertRaises(render.MotionError):
            render.render(self.project,out,preset="ultrafast")
        self.assertEqual(out.read_bytes(),b"do-not-overwrite")

    def test_zip_rejects_traversal_and_duplicate_entry(self):
        if not self.project:self.skipTest("FFmpeg is required")
        z=self.root/"invalid.zip"
        with zipfile.ZipFile(z,"w") as archive:
            archive.writestr("../outside.mp4",b"bad",compress_type=zipfile.ZIP_STORED)
        with self.assertRaises(render.MotionError), render.project_source(z):
            pass
        z2=self.root/"duplicate.zip"
        with zipfile.ZipFile(z2,"w") as archive:
            archive.writestr("storyboard.json","{}",compress_type=zipfile.ZIP_STORED)
            archive.writestr("storyboard.json","{}",compress_type=zipfile.ZIP_STORED)
        with self.assertRaises(render.MotionError), render.project_source(z2):
            pass

    def test_real_zip_with_audio_and_photo_extraction(self):
        if not self.project:self.skipTest("FFmpeg is required")
        z=self.root/"valid.zip"
        with zipfile.ZipFile(z,"w",compression=zipfile.ZIP_STORED) as archive:
            for path in (self.project,self.root/"assets/photo.png",self.root/"assets/sound.wav"):
                archive.write(path,path.relative_to(self.root).as_posix())
        with render.project_source(z) as project:
            self.assertEqual(render.load_project(project)["soundtrack"],"assets/sound.wav")
        self.assertFalse((self.root/"outside.mp4").exists())

    def test_ffmpeg_real_720p_h264_two_scene_with_aac(self):
        if not self.project:self.skipTest("FFmpeg is required")
        if not shutil.which("ffprobe"):self.skipTest("ffprobe is required")
        out=self.root/"rendered.mp4"
        report=render.render(self.project,out,crf=28,preset="ultrafast",threads=2)
        self.assertEqual(report["status"],"RENDERED_LOCAL_ONLY")
        self.assertEqual(report["duration_seconds"],2)
        self.assertFalse(report["ai_video_model_used"])
        self.assertFalse(report["upload_performed"])
        self.assertTrue(out.stat().st_size>8000)
        probe=subprocess.run(["ffprobe","-v","error","-show_streams","-show_format",
                              "-of","json",str(out)],check=True,capture_output=True,text=True,timeout=15)
        p=json.loads(probe.stdout)
        video=next(stream for stream in p["streams"] if stream["codec_type"]=="video")
        audio=next(stream for stream in p["streams"] if stream["codec_type"]=="audio")
        self.assertEqual(video["codec_name"],"h264")
        self.assertEqual([video["width"],video["height"]],[1280,720])
        self.assertEqual(audio["codec_name"],"aac")
        self.assertAlmostEqual(float(p["format"]["duration"]),2,delta=.2)

    def test_all_file_inputs_use_strict_local_ffmpeg_protocols(self):
        source=script.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('"-protocol_whitelist", "file,pipe"'),4)
        self.assertNotIn('"http,https"',source)

    def test_no_shell_network_or_autonomous_media_uploader(self):
        source=script.read_text(encoding="utf-8")
        for forbidden in ("shell=True","requests.post(", "urllib.request", "os.system(",
                          "gh release", "AWS_SECRET", "subprocess.Popen("):
            self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main(verbosity=2)
