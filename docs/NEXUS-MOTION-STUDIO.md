# NEXUS Motion Studio — original offline video & animation

**Implementation date:** 2026-11-18. **Authority:** none.

NEXUS Motion is a **real**, user-directed and local video/animation production
tool. It is **not** a trained text-to-video diffusion model, a Runway/Sora
equivalent, an unlimited free GPU, a hosted job queue, or a proof of professional
film output. It does not impersonate people, edit facial features, or secretly
upload image, audio or project data.

## Usable outputs

- Browser editor: `/motion` on the NEXUS Rust HTTP server; available from the
  NEXUS home page. On Android, preview and edit scenes without paid tools.
- Procedural visual animation: gradients, organic parallax light, concentric
  motion, timed original titles and subtitles, fades, an editable timeline,
  five motion paths and optionally locally selected **original** photographs
  displayed without aspect-ratio distortion.
- Mobile video capture: a real-time MediaRecorder **WebM or MP4**, whichever the
  browser actually supports. Each segment is limited to **15 seconds** and
  browser export is capped at **1080p, 30 fps, and 96 MiB**. The user can choose
  consecutive segment start times. Audio can be added from a local file using
  the browser's Web Audio mixer (depending on browser support). No local
  source content is uploaded.
- Downloadable storyboard JSON + original assets/soundtrack ZIP, implemented in
  pure JavaScript with STORE entries and CRC-32. ZIP requires ≤96 MiB total
  media and runs entirely in the browser; large source media can instead be
  transferred alongside the JSON. No unprompted local persistence.
- **FFmpeg MP4 renderer:** H.264 yuv420p with quality-controlled CRF (10–30),
  fast→slow CPU presets, stereo-capable AAC soundtrack, 24/25/30/60 fps,
  landscape Full HD and 4K and vertical HD/4K. It renders each storyboard scene
  to a separate local segment, joins them with stream copy, and only then
  replaces the final output atomically. Large clips are processed sequentially,
  without accumulating all decoded frames in browser memory.
- Scene count 1–120; one scene 1–900 seconds; whole project up to 7200 seconds
  (two hours) per job. Limits are a defensive admission policy, **not**
  a speed/performance guarantee. Extend only with additional measurements.

## Formats and high quality

| Type | Native browser | Offline FFmpeg |
| --- | --- | --- |
| Preview | Canvas 2D | Full rendered MP4 |
| Resolution | Small preview; export ≤1080p | HD, Full HD, 4K, vertical HD/4K |
| FPS | Capture ≤30, if supported | 24, 25, 30, 60 |
| Duration | ≤15 sec per downloaded segment | ≤2 hours per project |
| Movie file | Supported WebM/MP4 MediaRecorder | H.264 MP4 |
| Music | Selected user audio (browser support varies) | Selected WAV/MP3/etc to AAC |
| AI video model | No | No |
| GPU/cloud service | No | No |
| Publishing/deployment | Never automatic | Never automatic |

Actual 4K speed, file size and usable recording length depend on CPU/GPU,
device storage, available memory, thermal throttling, installed FFmpeg and
the filesystem. High visual quality is a user-tuned encoding **goal**, not a
claim of cinematographic or photorealistic synthesis.

## Android workflow without paid apps

1. Open `/motion` in the NEXUS site **after this PR has been merged and
   deployed**. Until then, preview the PR source or run the local site.
2. Edit title, scenes, camera movement, format, fps, optional photos and music.
3. Use Play for local preview and Record for a 1–15-second browser clip.
4. Download a project ZIP containing `storyboard.json` and the selected
   assets. For larger inputs use the JSON export and transfer original files
   into a sibling `assets/` directory manually.
5. For continuous high-resolution MP4, a locally installed Termux environment
   with Python 3, FFmpeg/ffprobe, sufficient free disk and a font is needed:
   `pkg install python ffmpeg unzip`. Obtain this repository's
   `scripts/nexus-motion-render.py` from the reviewed commit; no provider key
   is involved. Example:

   ```sh
   unzip "NEXUS-project.zip" -d project
   python3 nexus-motion-render.py project/storyboard.json movie.mp4 --crf 18 --preset medium
   ```

   Or pass the STORE ZIP directly:
   `python3 nexus-motion-render.py NEXUS-project.zip movie.mp4 --crf 16 --preset slow`.

`--check` validates the project without rendering. `--font` accepts a local
TTF/OTF if a suitable system font is not found. A lower CRF generally means a
larger file/higher fidelity. A 4K/60 fps/long project on a midrange Android
phone may take **far longer than real time**, fail due to storage/thermal limits,
or require a stronger CPU; NEXUS makes no free cloud compute promise.

## Source/quality and security boundaries

- The same `nexus.motion.storyboard.v1` contract is validated by JS and
  Python. Projects cannot reference arbitrary external URLs, execute a shell,
  or reach outside their media folder.
- Python FFmpeg calls use an argument list, `shell=False`, a fixed supported
  output profile, bounded input and temporary files and atomic final output.
  ZIP imports reject traversal, duplicate paths, symlinks, unexpected entries
  and unsupported compression; projects are under a strict resource budget.
- User titles are isolated in temporary UTF-8 text files to prevent FFmpeg
  filtergraph injection; filenames are separate argv values.
- Motion has no personal-account auth service, payment/deployment privileges,
  unrelated content access, script evaluation or background jobs.
- Browser photo loads use local `blob:` URLs; original photo aspect is
  maintained, and no hidden face edits are performed. Explicit animated zoom
  modes can change *visible crop*, unlike the still mode.
- This v1 engine produces stylized procedural animation, photo movement,
  typography and edited sound. A true natural-language generative video
  capability would require a separately authorized AI video model, real
  inference hardware or provider connection, moderation, provenance, cost
  and latency controls, plus quality assessments.

## Acceptance evidence

- `scripts/test-nexus-motion-core.mjs`: deterministic storyboard/timeline
  tests, high-res presets, adversarial values and route checks.
- `scripts/test-nexus-motion-render.py`: rejects path and ZIP attacks and
  runs a real two-scene 720p H.264/AAC FFmpeg render, checked with ffprobe.
- `scripts/test-nexus-motion-browser.py`: disposable real Chromium editor,
  local ZIP/JSON and MediaRecorder video output, with zero network calls.
- `.github/workflows/motion-studio.yml`: checks JS/Python and Rust gateway
  tests in a **read-only** GitHub Actions job. Passing CI does not prove
  Android hardware acceptance, 4K throughput, or public deployment.
