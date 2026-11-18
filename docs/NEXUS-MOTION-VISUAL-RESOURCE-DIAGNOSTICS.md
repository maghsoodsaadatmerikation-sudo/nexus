# NEXUS Motion v1.3: visual warnings and disk/resource planning

**2026-11-18 · local and experimental · draft PR only.**

This update addresses two **bounded** operational problems for large original
animations. It does **not** solve the remaining Canvas/FFmpeg pixel-parity gap,
create a text-to-video neural model, or prove production 4K throughput on Android.

## 1. Estimate what a long project might cost locally

`scripts/nexus-motion-diagnostics.py plan` reads the same validated storyboard
JSON or original-asset ZIP as the Motion renderer. It computes duration, frame
count, single uncompressed RGBA frame memory and a **planning-only** disk
estimate. It assumes H.264 12 Mbps at 1080p/30fps, scales that assumption by
pixels and frame rate, and budgets concurrent temporary segment/concat/final
MP4 files, 256 kbps audio (if present), plus 512 MiB to 2.5 GiB of headroom.

This formula is an **assumption, neither a hard upper nor a lower bound**:
real H.264 CRF size varies widely with detail, noise and motion; x264 may
temporarily need much more RAM than a single RGBA frame. Thermals, CPU/GPU
throughput and remaining battery cannot be inferred from this report.

```sh
python3 scripts/nexus-motion-diagnostics.py plan project.zip --output-dir .
```

The same planning formula is also exposed **inside the mobile Motion
storyboard editor** as a live advisory panel. It displays expected frames,
assumed bitrate, estimated staging storage, and suggested batch size as the
resolution, FPS, duration or soundtrack changes. Browsers cannot reliably
read the actual device's free disk space in this implementation, so the UI
explicitly shows **no measured free-space claim**. Use the local CLI above
to compare the estimate against actual filesystem free bytes.

The JSON includes `free_space_below_recommendation`, the available bytes,
`estimated_peak_local_bytes`, an absolute-minimum 128 MiB warning,
`render_speed_guaranteed: false` and a **recommended manual batch size**.
This command **does not start a render**, allocate disk or upload anything.

For longer 4K work, prefer small batches, sufficient local free space, a
charged/cooled device and a reliable backup of the original ZIP. There is
no unlimited cloud storage or free GPU allocated by NEXUS.

## 2. Sample limited parts of a completed MP4 for visual defects

`scripts/nexus-motion-diagnostics.py scan` uses the local FFmpeg CLI
to decode short windows at the **beginning, middle and end** of an MP4.
Each window is at most two seconds; visual analysis is limited to a reduced
320px-wide sample to keep the detector's frame memory bounded.

```sh
python3 scripts/nexus-motion-diagnostics.py scan movie.mp4 --duration 120
```

The `blackdetect` and `freezedetect` filters produce advisories:
the report shows sample offsets and counts of dark/frozen intervals. **A
deliberately still shot, a black title card, an intentional fade or a slow
motion shot may correctly trigger warnings.** No artistic judgement or
automatic rejection follows. This does not inspect the entire film or
guarantee absence of defects between sampled windows.

When using the optional resumable renderer flag:

```sh
python3 scripts/nexus-motion-resume.py project.zip movie.mp4 \
  --crf 18 --preset medium --threads 2 --resume --visual-qc
```

the sampled diagnostic runs **after mandatory frame-count/audio technical
quality verification but before the final MP4 is atomically committed**.
The report is written to `movie.mp4.motion-work/visual.json` with an
fsynced temporary checkpoint; the render summary exposes
`visual_review_suggested` and `visual_report`. Advisory warnings do not
block the local output. If the explicitly requested scanner itself fails,
the final MP4 remains untouched and its resumable work cache remains.

For an initial render omit `--resume`, as before. The content of the
`visual.json` file must not be treated as a release authorization, full
decoding test or a perceptual score.

## What still differs between live preview and final FFmpeg render

The browser Canvas uses animated gradients, particle lights, ellipse
geometry and system fonts. Native FFmpeg uses procedural grids, different
compositing, font metrics and zoom interpolation. The timeline/project
schema is shared, but **pixel-level parity has NOT been implemented or
verified**. Use a short encoded test MP4 for any important editorial
decision and review it directly on the target device.

## Verification

- Actual local black/frozen synthetic MP4 is decoded and reported as a
  **review warning, not a failed film**.
- Actual resumable H.264/AAC output is produced with the opt-in sampled
  visual report; output still passes strict packet/audio verification.
- Synthetic 4K/60fps resource plans and pathological/zero-disk cases
  prove conservative warnings and no overclaim of performance.
- A deliberately failed diagnostic run verifies existing user MP4 bytes
  are preserved even when `--force` was requested.
- Independent unprivileged GitHub Actions workflow
  `.github/workflows/motion-diagnostics.yml` contains no token authority
  to upload, merge, release or deploy.

Prior Motion PRs: #290 (studio + 720p/real Chromium export), #291 (resumable
FFmpeg), #292 (exact frame/AAC packet gate). This feature remains stacked
above them; all are separately reviewable. **No automatic main merge.**
