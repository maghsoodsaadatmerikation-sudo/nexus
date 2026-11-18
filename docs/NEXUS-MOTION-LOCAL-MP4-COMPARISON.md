# NEXUS Motion — Local decoded-MP4 vs Canvas comparison

**Stage:** unmerged, read-only user-controlled preview feature, 18 November 2026.

## Problem addressed

The Canvas editor and native FFmpeg renderer currently use **different**
gradient, particle, text, camera and color algorithms. The earlier video
codec/frame-timing checks do not prove that the visible frames correspond
to the preview shown on the phone.

This change provides a **real, measurable discrepancy report**, not a
claim that the renderers have become pixel-identical.

## Mobile workflow

1. Edit the storyboard in `/motion` and locally export/rerender it as MP4
   using NEXUS Motion's FFmpeg CLI or resumable renderer.
2. Open the **Compare real MP4** area in that same `/motion` page.
3. Select the **local .mp4 file**. The app does not upload or copy the
   video into JavaScript memory. The browser decodes it through a
   device-local `blob:` URL.
4. Play/seek the original storyboard preview. Click **Compare current
   frame** or **Compare 3 scenes** to inspect the native export at matching
   storyboard timestamps.
5. The local report shows normalized RGB absolute pixel error, the
   worst sampled discrepancy, and a warning count. Two renderers with
   substantial differences will have a high error: **do not represent
   a high score as successful visual parity**.
6. Clear local video to revoke the private object URL.

## What is measured

- Source video dimensions must exactly equal selected storyboard dimensions.
- Duration must agree within at most the configured bounded tolerance.
- The video is paused and decoded to the seek timestamp in the browser.
- Both Canvas preview and the actual MP4 video frame are downscaled
  to 320 pixels wide at the same aspect ratio, capped at 600 pixels tall.
- The pure JavaScript pixel comparator computes per-RGB-channel
  normalized mean absolute error (0 to 1), normalized RMS error
  and the fraction of pixels whose mean RGB difference is at least 25%.
- Error at or above 8% adds a **human-review warning**, not a technical
  render failure. One or three timeline positions are compared;
  timestamps are scene midpoints to avoid intentional fade boundaries.
- The page is CSP-constrained with `connect-src 'none'`; it does not
  use remote provider APIs, upload media, infer identity, change faces,
  rewrite the user movie or publish content.

## Important nonclaims

A numerical comparison **does not automatically correct** any mismatches
between FFmpeg and Canvas. The image may differ due to fonts, colors,
image paths, artistic effects, chroma subsampling, color profiles, frame
time rounding and scaling. A zero difference for a sampled frame does
not prove full-film continuity or equality. File identity is **not
cryptographically tied** to the original storyboard: the user must select
the appropriate movie manually. A mismatch can come from choosing an
unrelated MP4 and must not be misattributed to the rendering engine.

There is no generative text-to-video model, no unlimited cloud 4K GPU,
no new permission grant, no automatic video fixes or runtime
deployment. Full-frame objective parity, character motion consistency,
HDR and multi-minute 4K/60 fps throughput remain future engineering work.

## Evidence

- `scripts/test-nexus-motion-core.mjs`: bounded sample timestamps,
  exact equal vs black/white pixel pairs and rejection of malformed
  data/large buffers.
- `scripts/test-nexus-motion-compare-browser.py`: uses FFmpeg to encode a
  synthetic local H.264 movie, loads it into real headless Chromium via
  an original local File, decodes frames, compares one and multiple
  timestamps to Canvas, rejects a wrong-dimension movie, revokes
  the local blob link, and proves no page-side `fetch` calls.
- `.github/workflows/motion-preview-compare.yml`: two read-only PR jobs,
  one pure JS and one actual private Chromium/FFmpeg test. These
  tests do **not** attest to Android device performance or a deployed site.

All existing stacked PRs remain draft and **no merge or deployment is
authorized by this addition**.
