# NEXUS Motion v1.2 — technical video quality and 4K encoding acceptance

Date: November 18, 2026. **Experimental, local, unmerged**. This change is
stacked on the Motion Studio #290 and resumable renderer #291.

## Why this is a separate quality gate

Previously the resumable renderer checked a completed MP4's file existence,
codec, resolution, average frame rate and *approximate duration*. Those
checks did **not** detect a shortfall in total video packets/frames or AAC
audio coverage, and could misleadingly treat a truncated mux as complete.

This update adds `scripts/nexus-motion-quality.py` as an **independent,
read-only** file auditor. The resumable renderer now invokes it **before**
atomically replacing the user's final MP4. If the audit fails, the existing
final output is preserved and the resumable scene workspace remains intact.

It also writes `movie.mp4.motion-work/quality.json` (atomic, fsynced JSON)
containing the exact SHA-256 of the audited video bytes, stream dimensions,
frame count, audio metadata and the scope of the audit. The file is **not a
cryptographic signature** or proof of trustworthy hardware; it is a local
technical report.

## What is actually checked

- One and only one H.264 video stream with yuv420p pixels and exact expected
  dimensions; no hidden/unexpected streams.
- Expected integer fps 24/25/30/60 and **exact frame packet count** equal to
  `storyboard_duration_seconds × fps`, including after scene concatenation.
- Video start, video duration and container duration within strict bounded
  tolerances.
- When a soundtrack is requested, one AAC stream with positive packet count,
  valid sample rate/channel count, start near time zero and coverage to within
  0.25 seconds of the expected final duration.
- Streaming SHA-256 of the entire MP4 (constant-size read buffer).
- Explicit denial of symlink/empty files and malformed ffprobe output.

`ffprobe -count_packets` reads the container's packet-level information,
which is far cheaper for a two-hour movie than fully decoding every pixel.
This is **not** a full bitstream decode, visual perceptual score, color
grading audit, HDR test, face-consistency assessment or anti-flicker model.
Genuine creative quality still needs direct visual review.

## Example usage

The existing local resume tool now runs this technical audit automatically.
Its final result includes `technical_mp4_verified: true` and
`quality_report` pointing to the local generated JSON.

The standalone audit is useful for reviewing an exported film:

```sh
python3 scripts/nexus-motion-quality.py movie.mp4 \
  --width 1920 --height 1080 --fps 30 --duration 90 --audio
```

The declared parameters must be the **actual** storyboard dimensions and
duration. Leave off `--audio` only when the movie was intentionally made
without a soundtrack.

## 4K capability: narrowly supported claim

The new independent CI test actually runs FFmpeg to encode a **single**
3840×2160 H.264 frame and reads the resulting container with ffprobe. It
demonstrates a 4K encoding code path on that CI machine. It **does not**
demonstrate sustainable high-quality long-form 4K rendering, 4K/60 fps
throughput, GPU access, Android thermal behavior, HDR output, or a trained
AI video model.

The existing real acceptance additionally renders and inspects full
two-scene 720p/24fps H.264/AAC files, verifies exactly 48 video packets
and tests audio/non-audio mismatch rejection.

## Resource, privacy, and authority

- No media file is uploaded or submitted to an external inference API.
- ffprobe uses a separate subprocess argument list and a 90-second timeout
  per audit operation. The full MP4 is hashed locally.
- All repository CI has read-only GitHub contents permission.
- Large projects need significant storage for cached MP4 segments and final
  output. The previous minimum-disk-space guard is still a minimum,
  **not** an estimate of the eventual multi-GB footprint.
- The output has `release_authorized: false` and
  `artistic_quality_assessed: false`. No deployment, no paid provider.
- The user can work on Android via Termux, but all live CI was executed
  on hosted Linux, **not on their personal phone**.

## Next known engineering gaps

True Canvas-preview and FFmpeg-render pixel parity, long-film audio edits,
timecode-aware subtitle layouts, hardware-specific 4K throughput tests, visual
motion consistency scoring and sustained storage benchmarking remain open.
