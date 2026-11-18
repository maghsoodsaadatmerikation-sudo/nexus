# NEXUS Motion v1.4 — sampled scene-boundary continuity diagnostics

**Implementation:** 18 November 2026. Draft, local-only, stacked on PR #293.
No trained generative text-to-video model, remote GPU or publishing capability.

## Problem and scope

NEXUS Motion already validates a video file's codecs, number of packets,
dimensions and audio, and optionally warns about black/frozen imagery in
three short sampled windows. That does not inspect the **edit point between
separate scenes**, where an unintended abrupt jump can disrupt the narrative.

New `scripts/nexus-motion-seams.py` extracts exactly two short
**decoded, low-resolution luminance frames** at an evaluated scene boundary:
the frame just before the cut and the next frame. The visual difference
is the normalized mean absolute luminance difference (0 = unchanged,
1 = maximum black-to-white). An observed score at or above `0.24`
adds an **EDITORIAL WARNING**, not a failed MP4 claim.

A sharp cut can be a creative choice. The detector cannot diagnose
continuity of characters, object trajectories, camera direction, color
grading, musical beat synchronization, or psychological narrative.
A small luminance score does not guarantee good motion continuity.
This check does not create transitions or smooth video automatically.

## Limits for phone and long-duration projects

At most **24 of 119 scene boundaries** are sampled, including the first
and last for multi-boundary projects; on two-scene projects, their single
cut is sampled. Each frame is scaled to `64×36` grayscale before comparison.
FFmpeg seeks by frame timestamp in the file's already verified constant
frame rate; it does not keep decoded full-4K frame sequences in memory.

For very long files, indexed seeking can still be expensive and depends on
container/keyframe layout. The script has a 45-second timeout per frame
extraction; worst-case scanner runtime is not a 45-second total budget.
Bounded sampling is **not full-film analysis**.

## Usage with Android Termux/Linux FFmpeg

To inspect a completed movie using an unchanged local storyboard:

```sh
python3 scripts/nexus-motion-seams.py project.zip movie.mp4
```

To request optional seam checks during resumable MP4 creation:

```sh
python3 scripts/nexus-motion-resume.py project.zip movie.mp4 \
    --crf 18 --preset medium --threads 2 --seam-qc
```

After a manually paused batch, pass `--resume` with the identical render
profile and inputs. A `seams.json` report is atomically written alongside
the existing `quality.json` in the owner-only
`movie.mp4.motion-work/` directory. The check runs **after mandatory**
H.264/AAC packet validation, but **before atomic replacement** of an
existing final output. A requested scan's technical failure leaves a
preexisting user MP4 untouched. Warnings alone are never an error.

The report exposes `boundaries_flagged`,
`pixel_parity_with_canvas_proven: false`, `render_failure: false`,
and `release_authorized: false`.

## Real acceptance contract

- Decode a real H.264 movie formed by a black first second followed by a
  white second second; its boundary must be flagged.
- Decode a black-to-black movie; its boundary should not be flagged.
- Test sample-selection limits, impossible frame formats, and symlink denial.
- Test that a real two-scene NEXUS H.264/AAC render produces an independent
  `seams.json` and retains the original strict quality gate.
- Inject a scanner failure and assert that the user's preexisting output
  bytes are unmodified, even with explicit `--force`.
- The read-only workflow is `.github/workflows/motion-seams.yml`.
  Passing these narrow tests is not an Android hardware throughput test.

## Remaining gaps

The browser Canvas and native FFmpeg renderers still differ in gradients,
particles, fonts and motion interpolation. **Pixel parity is not claimed**.
Sustainable multi-minute 4K rendering on actual Android hardware and real
character-motion preservation are not yet demonstrated. This diagnostic
is groundwork for evidence-based improvements, not a visual quality score.

No public NEXUS deployment or main branch merge has occurred from this PR.
