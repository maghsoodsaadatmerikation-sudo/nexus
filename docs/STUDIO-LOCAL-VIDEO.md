# NEXUS Studio — free local image-to-video composer

**Status:** source candidate in a stacked draft pull request, not a
production release or a hosted generative video model.

## What users can do

Inside chat-first Studio, open **Make video**, select **1–4 PNG/JPEG images** (bounded to 6 MB each, 16 MB combined and
16 megapixels decoded in total), reorder or remove scenes, or explicitly copy
one image-generation preview from the same browser tab,
choose landscape (640×360) or portrait (360×640), select a 3, 6, 10 or
12-second total duration and opt into a gentle fade at the beginning/end
and a short crossfade between successive images.
Optionally select a short audio track and press **Record locally**.

The composer uses the browser Canvas captureStream, MediaRecorder and,
for audio, Web Audio's MediaStreamDestination. It makes a real video file
only if the browser supports the selected encoding. It never contacts a
video provider or requires a model API key. Users can preview, stop and
discard, clear or explicitly download the completed clip.

Each source photo is fitted within the frame; neutral letterbox
space is used rather than cropping. **No zoom, face/body edits, generative
animation, camera motion, subtitles, automatic sharing or YouTube publishing**
is performed. Motion is limited to optional fade-in/out and transitions
between still images; the storyboard automatically divides total duration
equally among scenes rather than supporting per-scene timing.

## Technical boundaries

- Storyboard: 1–4 PNG/JPEG photos, up to 6 MB per image / 16 MB combined;
  each photo is at most 4,096 pixels per side and 8 megapixels, and total
  decoded pixels may not exceed 16 million. Decoding happens locally.
- Audio: optional user-selected WAV, MP3, OGG or M4A (subject to browser
  codec support), up to 8 MB, decoded duration at most 30 seconds. Only the
  selected video duration is captured; remaining audio is discarded.
- Video: 640×360 or 360×640; 20 FPS target; chosen duration 3–12 seconds;
  MediaRecorder tries WebM/VP8+Opus, WebM/VP9+Opus, WebM, then MP4 if
  supported. Browser scheduling may make the actual duration approximate
  rather than frame-perfect. Output is bounded to 32 MB.
- No automatic upload, model call, project storage or addition to encrypted
  chat history. Media and temporary object URLs are cleared on explicit
  clear or a conversation change.
- The original image/audio files are not overwritten. The original photo
  remains uncropped in the rendered frame.
- Unsupported browsers must leave Record disabled rather than pretending
  to produce a video. Browser crash, tab closure or background throttling
  may interrupt recording. Low-memory devices may struggle with decoding.
- User-downloaded files are saved in locations outside NEXUS's control.

## Testing and release gates

The real Chromium static acceptance test exercises a synthetic local photo,
portrait layout, a two-image synthetic color preview with reorder, an actual
MediaRecorder clip when supported, resulting
file header and size, exclusion from project storage, and clear. Unsupported
MediaRecorder configurations fail closed. This does not prove real Android
device support or test every browser/codec.

The reviewed Studio module graph explicitly admits the new video module;
no dynamic loader or extra outbound request is introduced. Standalone and
public static bundles with offline-worker SHA-256 integrity must remain
byte-for-byte reproducible, with a bounded public file inventory.

Do not merge or publish until source-bound CI checks pass and the preceding
image generation pull request is reviewed and merged.

## Still missing

This phase does **not** implement generative image-to-video AI inference,
arbitrary scene lengths, layered text effects, precise timeline/keyframes,
exact audio/video synchronization, voice recording,
high-resolution offline MP4/H.264 exports, or video uploads. These require
separate engineering and real-device verification.

NEXUS principle: AI assists human judgment without assuming its authority.
