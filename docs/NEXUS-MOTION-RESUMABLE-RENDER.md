# NEXUS Motion v1.1 — resumable and tamper-detecting local render queue

**Implementation:** November 18, 2026. No hosting, provider, GPU, inference
model, publisher or privileged GitHub automation is provisioned.

## The interruption bug addressed

Earlier `scripts/nexus-motion-render.py` used a temporary directory for
every run. On Ctrl+C, Android thermal shutdown, missing disk, failed scene or
process restart, all completed temporary scene MP4 files disappeared, so a long
4K/60 fps project had to restart from scene 1.

The new `scripts/nexus-motion-resume.py` adds an opt-in, **explicitly
resumable** render workspace next to the requested output. It preserves
successfully finished scenes, supports small manual battery/thermal-friendly
batches, and verifies existing cached bytes before reuse.

## Usage from an Android Termux shell (or local Linux)

Install Python 3, FFmpeg with ffprobe and a local TTF/OTF font. Save the
storyboard JSON + its `assets/` folder, or use the ZIP exported by the browser
Motion UI. This script requires Linux `fcntl.flock` (Android/Termux supports
it); no model key, provider, cloud account or Python dependencies beyond the
standard library.

First batch:

```sh
python3 scripts/nexus-motion-resume.py project/storyboard.json movie.mp4 \
  --crf 18 --preset medium --threads 2 --max-new-scenes 3
```

Then continue:

```sh
python3 scripts/nexus-motion-resume.py project/storyboard.json movie.mp4 \
  --crf 18 --preset medium --threads 2 --max-new-scenes 3 --resume
```

Run the same command without `--max-new-scenes` to finish all remaining
scenes. When all scenes are verified, it joins them and optionally mixes the
original soundtrack into H.264/AAC MP4.

To build from a browser-exported ZIP, replace `project/storyboard.json` with
`project.zip`. The ZIP is unpacked only into a bounded temporary local
directory; the cache fingerprint uses **media content**, not temporary
extraction paths. It can therefore continue across fresh ZIP extractions.

An existing final `movie.mp4` will **never be overwritten** unless the owner
passes `--force`; even then, replacement happens only after complete output
verification. If rendering crashes during a scene, a `.partial.mp4` file is
not trusted or reused. It is rewritten on the next attempt, but completed
earlier scene files remain.

## Security and reliability guarantees (within the tested boundary)

- The render workspace is named `movie.mp4.motion-work/`, is created with
  private permissions and denied when an unrecognized file, symlink or unsafe
  workspace mode is found. It is never recursively cleaned behind the user.
- Linux `flock` allows one live writer per workspace. The lock releases if a
  process dies. No remote or background job is started.
- The manifest is atomically checkpointed and fsynced after each successful
  scene. It binds the exact storyboard structure, the SHA-256 of every original
  photo and soundtrack, font digest, both renderer scripts, FFmpeg version,
  CRF, preset and thread count. Changing any of these prevents stale reuse.
- Every claimed reusable MP4 is rehashed **and independently probed** for H.264
  codec, dimensions, exact frame rate, duration and absence of soundtrack.
  A corrupted or substituted file is rendered again, rather than trusted.
- Before each scene, local free disk is rechecked (minimum 128 MiB) and each
  render is bounded by a timeout. This is a **minimum safety threshold, not a
  prediction of actual space needed for hours of 4K media**.
- The final video and optional AAC audio are checked with ffprobe before
  replacing the user-selected output. Intermediate failures do not replace a
  pre-existing file.
- Current two-hour/120-scene admission budget remains unchanged. Native
  4K/60 fps **performance and Android battery/thermal behavior are not yet
  benchmarked**. No quality claim for AI photorealistic generation is made.
- On every resumed run the original source media must remain available and
  unchanged. Changed media intentionally invalidates the entire checkpoint.
  Changing code or FFmpeg build also forces a new workspace.

## Operator recovery

If input/media settings change, choose a **new output filename** and run
without `--resume`. The older cache remains untouched for explicit review or
manual deletion. Never delete an existing cache directory while a render
process holds it. Inspect `movie.mp4.motion-work/manifest.json` for finished
scene metadata. A valid manifest is not a signature, authorization grant or
evidence of anything outside the owner's local machine.

## Verification

`scripts/test-nexus-motion-resume.py` tests:
- real pause after scene one then continuation and valid two-scene H.264/AAC MP4;
- SHA-256 tampering and stream identity rejection;
- changed soundtrack, CRF and thread-count fingerprint failures;
- duplicate JSON and malformed cache rejection;
- symlink and unexpected workspace files;
- concurrent Linux lock failure;
- recovery from a ZIP unpacked in two different temporary locations;
- explicit force only and refusal to overwrite user output after failure.

All tests execute in a read-only CI job
`.github/workflows/motion-resume.yml`. A green test does **not** prove
Android hardware, large-volume throughput, merge readiness or production
deployment. The workflow also enforces Rust formatting after the original
Motion PR's formatting failure.

Authority invariant: `A_out <= A_in`. No merge or release is automatic.
