# NEXUS Music Lab — native, local music composition and audio synthesis

**Implemented scope (v1):** a real deterministic, offline-first instrumental
composition engine integrated into NEXUS Studio. It does **not** call Suno,
generate Suno prompts, scrape services, require a vendor subscription or send
material to a hosted AI model. This is a **locally synthesized original music
engine**, not a trained singing model or a virtual recording studio.

Source modules: [composition + DSP](../web/studio-music.js),
[Studio UI](../web/studio-music-ui.js), [CI tests](../scripts/test-studio-music.mjs).
Studio's existing reproducible packaging embeds both modules directly into
`web/studio.html` and the independently pinned static offline PWA
`public/studio/index.html`.

## What runs today

Open NEXUS Studio and select **Music Lab / موسیقی** from the tools list,
including the mobile Tools menu. Pick story, eastern-influenced tonal mode,
tonic, tempo, length, melodic lead and prominent solo, with explicit optional
santur answering, electric guitar foreshadowing and daf rhythm.

**Compose** calculates an original event-level score containing separate
piano, santur, oud, ney, kamancheh, cello, electric guitar and daf tracks.
The deterministic event generator is built around a repeating/revised motif,
bar-aligned sections (threshold → motif → dialogue → ascent → solo → summit
→ return), phrase gaps, sparse harmonic gravity, and an actual exposed solo.
Each score contains source settings, full note events and a structural review.
Variations change the arrangement seed while *preserving the melody seed* by
default. Explicit self-critique controls can instead change the dominant
instrument or story arc, expand length, or revise the motif **if unlocked**.

**Download MIDI** exports Standard MIDI File type 1 with tempo, track-level
program changes, note-ons/offs, drums on MIDI channel 10, and dedicated
half-semitone pitch bend channels for microtonal voices. Pitch bend uses
the usual +/-2-semitone General MIDI convention; rendering on arbitrary
players depends on that instrument's bend-range setting and sample library.
The native WAV renderer uses note frequency directly and does not depend on
a receiving MIDI synthesizer's tuning. It intentionally avoids a generic
"oriental instrument" label by modelling distinct bright struck/plucked,
airy/blown, bowed and distorted spectra.

**Synthesize WAV** renders stereo 16-bit PCM locally at 22.05 or 44.1 kHz;
the WAV can be previewed and downloaded, without an upload or API request.
Rendering is cancellable, yields between small chunks on the UI thread,
uses normalized headroom and a gentle audio tail. MIDI and WAV are generated
from the **same event score**, with explicit 32-, 48- and 64-bar selections.
This is original generated data, not a derivative of a protected song.

## Lessons carried into the architecture

- **Short, flat tracks:** A 64-bar default and seven distinct energy phases
  prevent unconditional two-minute endings and encourage narrative contrast.
  Time is computed from BPM/bars, not claimed as a generative runtime guarantee.
- **Weak hook:** An explicit motif seed gives repeatable thematic identity;
  variations preserve it by default instead of silently replacing everything.
- **Santur/oud/ney/kamancheh confusion:** Each part has explicit pitch,
  role, tessitura, attack/decay and synthetic harmonic envelope. These sounds
  are deliberately approximate; they are **not** sampled acoustic instruments.
- **Guitar and santur solos disappearing:** Main solo role is explicitly
  isolated in score events; electric-guitar prelude and closing santur response
  can be selected as distinct roles, and the structural diagnostic checks
  that the assigned solo exists.
- **One sound from beginning to end:** Arrangement varies instrument density,
  percussion, role handoffs, pauses and volume along the selected story arc.
- **Fixes undoing earlier gains:** The motif lock and explicit seed allow
  repeatable A/B comparisons; all downloaded files remain external to the
  tab. Objective warnings never override the artist's choices.
- **Invented phonemes / choir / original human lead vocal:** **Not available
  in this first native engine.** It does not pretend to clone the artist's
  voice or generate a real choir. The next vocal pathway should accept
  user-provided original takes through explicit local, private audio editing,
  not automatically manufacture a human performance.

## Artistic and technical limits

These musical scales are **stylized modal interval sets**, not historically
complete transcriptions of every Iranian dastgah, Arabic maqam, Turkish makam,
or a calibrated tuning system. Shur and Bayati require expert treatment of
regional tuning and ornamentation beyond the present seven-step templates.
The generated timbres are lightweight procedural approximations; a sampled
santur, bowed kamancheh, double-tracked oud, breath-shaped ney, expressive
electric guitar performance and real human voice would materially improve
realism.

Structural self-review only checks measurable properties (relative energy,
chosen solo, presence of required timbres, motif gaps, duration). It cannot
credibly determine beauty, catch real audio glitches by ear, claim emotional
resonance or estimate plagiarism. There is no AI listening model or automatic
microphone/recording analysis. It does not guarantee studio mastering or a
perfect psychoacoustic mix. Long high-rate renders consume phone CPU, memory
and battery; rendered files and seed settings are temporary until explicitly
downloaded.

No native recording upload, stem separation, melody-to-vocal alignment,
DAW-grade effects, sample licensing, VST integration, direct social upload,
Suno API or paid music-generation service is implemented. The existing
Studio release and public deployment checks remain separate. GitHub source
changes do not automatically publish a new Render-hosted Studio.

## Verification and staged path to higher quality

```sh
node scripts/test-studio-music.mjs
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
```

Dedicated CI runs deterministic composition, quarter-tone MIDI and local
PCM WAV assertions, malformed option rejection, builder checks and a
disposable real Chromium smoke test for the offline Studio package.

**Next engineering phases, not claimed as built:** (1) direct UI browser
render/export contract tests and reference A/B listening clips; (2) license-
verified, locally stored original instrument samples and velocity layers;
(3) ornaments, phrase articulation, multi-point expressive pitch bends,
regional maqam/dastgah intonation library with documented sources; (4)
user-owned vocal takes and optional local non-cloud processing; (5)
arrangement/mix quality analysis based on actual audio features and
independent listening evaluations. Any audio sample ingestion must be
user-consented, scoped to the active project and safe for encrypted export.

NEXUS's constitutional rule remains `A_out <= A_in`: music generation
creates creative material, not authority to publish, claim ownership of a
sample library, impersonate a singer or modify an external account.
