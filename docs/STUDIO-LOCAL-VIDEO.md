# NEXUS Studio — free local image-to-video composer

**Status:** source candidate in a stacked draft pull request, not a
production release or a hosted generative video model.

## What users can do

Inside chat-first Studio, open **Make video**, select a PNG/JPEG or
explicitly copy the latest image-generation preview from the same browser tab,
choose landscape (640×360) or portrait (360×640), select a 3, 6, 10 or
12-second duration and opt into a gentle fade at the beginning and end.
Optionally select a short audio track and press **Record locally**.

The composer uses the browser Canvas captureStream, MediaRecorder and,
for audio, Web Audio's MediaStreamDestination. It makes a real video file
only if the browser supports the selected encoding. It never contacts a
video provider or requires a model API key. Users can preview, stop and
discard, clear or explicitly download the completed clip.

The entire source photo is fitted within the frame; neutral letterbox
space is used rather than cropping. **No zoom, face/body edits, generative
animation, camera motion, subtitles, automatic sharing or YouTube publishing**
is performed. Motion is limited to optional fade-in and fade-out.

## Technical boundaries

- Photo: PNG/JPEG, at most 6 MB; decoded dimensions up to 4,096 per side
  and 8 megapixels. Decoding happens locally.
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
portrait layout, an actual MediaRecorder clip when supported, resulting
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
multi-scene timeline editing, exact audio/video synchronization, voice recording,
high-resolution offline MP4/H.264 exports, or video uploads. These require
separate engineering and real-device verification.

NEXUS principle: AI assists human judgment without assuming its authority.
