# Studio original-vocal asynchronous race protection — 2026-11-19

## Finding

The previous Orchestra UI used a render/mix `ticket` to reject outdated
file-read completions. Clicking **Remove original vocal** called
`clearDry()`, but that method did not advance the ticket. If a local
`File.arrayBuffer()` or subsequent SHA-256 operation was pending, its
completion could reintroduce the dry vocal WAV and a new Blob playback URL
*after the user had explicitly cleared the voice*. A late read failure could
also overwrite the cleared/locked page's status.

The simultaneous audition path awaited two `HTMLMediaElement.play()`
promises; their late resolution could produce a misleading "playing" message
after the private workspace was locked.

## Fix and invariants

- A dedicated monotonic `dryEpoch` advances whenever the private vocal is
  cleared or replaced, including lock, erase, or page unload.
- Each file import binds **both** the existing render/mix ticket and the
  independent dry-vocal epoch. It checks these identities after each await
  and before installing dry bytes or creating Blob URLs.
- Rejected stale imports cannot update status or button state.
- A simultaneous playback request also captures the render and voice
  generations, and cannot claim success or failure after either has changed.
- User initiated file clearing does **not** cancel unrelated score
  preparation or trigger remote network requests. Existing voice file
  validation and original-bytes guarantees are unchanged.

## Evidence

`scripts/test-studio-vocal-races-browser.py` uses an actual disposable
Chromium page, controlled synthetic WAV bytes and deferred promises to
reproduce:

1. a successful file read that resolves **after** explicit vocal removal;
2. a rejected read that completes **after** removal;
3. a successful read that resolves **after** locking the Studio;
4. subsequent legitimate new voice import and score rendering;
5. simultaneous playback promises that settle **after** lock;
6. no network calls for these local actions.

The test runs within `NEXUS Studio Verification`, while all existing
static-site and offline service-worker tests still check exact generated
asset integrity. The standalone HTML, public static HTML and offline
service-worker SHA/cache identity were regenerated alongside the source.

This is an in-tab UI race fix, not guaranteed physical memory zeroization,
deletion of an exported WAV or a claim of live production deployment.
