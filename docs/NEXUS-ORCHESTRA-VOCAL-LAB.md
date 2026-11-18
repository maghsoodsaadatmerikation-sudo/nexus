# NEXUS Orchestra & Vocal Lab — Native v1

**Status:** original offline orchestration in reviewed Studio source. GitHub changes do not automatically deploy to the live public site. This feature does not call Suno, an external music API, or a model account.

## Supported prompt-to-music work

Use the **Orchestra / آواز** tool in NEXUS Studio. Its strict, inspectable bilingual English/Persian grammar recognizes Western instrument families, five creative styles, voice register, tone, an optional synthetic three-part choir, tempo/length, major/minor key, electronic sound effects and synthetic animal-inspired effects. It displays *recognized words*, unknown terms, and conflicts before a score may be created. Unsupported terms **block composition** rather than being silently guessed.

Examples to paste into the prompt field:

- hypnotic airy soprano choir harp flute in D minor 92 bpm 8 bars bird chime
- operatic powerful soprano choir violin cello harp in C minor 84 bpm 8 bars
- rap bright tenor piano synth 110 bpm 8 bars pulse drums
- pop warm alto acoustic guitar flute 100 bpm 8 bars
- اپرا سوپرانو گروه کر ویولن ویولنسل چنگ تمپو 84

**This is NOT an AI that understands arbitrary natural language**. It is a limited, deterministic keyword grammar with explicit error reporting, not a text-to-music neural model.

The original composer can construct parts for grand piano, violin, viola, cello, double bass, flute, oboe, clarinet, French horn, trumpet, trombone, harp, pipe organ, acoustic guitar, synthetic pad, an original electronic vowel voice, high/mid/low electronic choir, drumkit, generic electronics and animal-inspired electronic cues.

Opera, rap, pop, hypnotic and chant change the generated contour, note timing and vowel articulation. Tone choices are airy, warm, dark, bright, soft and powerful; registers are soprano, alto, tenor and baritone. This creates only synthetic vowels such as Ah/Oo/Ee, **not intelligible sung language or realistic human performances**. Synthetic harmonies do not sample real singers and do not require a male vocal.

Animal cues such as bird, crow, owl, whale and cat are *electronic approximations*, not recordings of living animals. Likewise, orchestral instruments are procedural waveform families and not professional sampled or physically verified instruments. No copyrighted sound library is bundled.

## Notation and exports

- **MusicXML 4.0 partwise**: instrument parts, exact 4/4 measure divisions (480 ticks per quarter), tempo, pitches, note/rest duration, dotted rhythmic figures, major/minor signature, treble/alto/bass/percussion clefs and generated vowel syllable labels. Tests parse the actual exported XML and verify every measure sums to four beats.
- **Standard MIDI File type 1**: tempo/time-signature track, per-part GM programs and note events, percussion on channel 10.
- **Score JSON**: reproducible event sequence and prompt-derived configuration.
- **Stereo PCM16 WAV**: original local audio synthesis with synthetic vowels, rhythm, instruments and effects.

The MusicXML notation exporter uses fixed 12-tone major/minor Western pitch sets and discrete note durations. Advanced tuplets, user-edited engraving, notation import, microtonal real-time tuning and exact sung-lyrics alignment are not implemented here. The pre-existing Eastern Music Lab remains separate.

## Your original voice: no voice transformation

Only after you explicitly select a user-owned **PCM 16-bit WAV** (mono or stereo, 22,050 or 44,100 Hz, <=20 MiB, canonical 44-byte WAV header) does the browser read the file locally. It displays the SHA-256 fingerprint and provides byte-for-byte **Download original, untouched**. The source PCM is not pitch shifted, formant altered, time stretched, cloned, submitted for training, or sent to any service.

The older optional **Play vocal and backing together** audition still starts
two separate audio players at normal speed and is not sample-accurate. A new
independent **Align & Mix locally** button now produces a sample-aligned
stereo WAV copy. Its source is the fully synthetic orchestral backing WAV
plus a *user-authorized* user-owned dry PCM16 WAV, without a provider call.
The dry original remains byte-for-byte intact in browser memory and can be
downloaded independently.

Use a signed, integer offset from -3000 to +3000 milliseconds: positive
moves the original vocal later; negative moves **the backing later**, rather
than trimming the beginning of the vocal. Relative alignment is rounded to
the nearest PCM frame. Zero automatic onset detection is claimed: the artist
chooses the offset based on listening. Both sources must have an identical
22.05/44.1 kHz sample rate. If your original is 44.1 kHz, re-render backing
*after* importing the vocal; its rate will then match automatically. There
is **no resampling, formant or pitch transformation**.

Three conservative mixing settings adjust voice and backing levels only in
the *new mixed copy*. A two-pass PCM mixer scans exact linear sums before
export, then applies a common protective attenuation if the peak exceeds
-0.45 dBFS (95% amplitude). This prevents hard digital clipping while
explicitly reporting the applied level change. The mixed output waveform
**necessarily differs** from the original source, but the dry track is never
mutated. An opt-in **Instrumental backing, omit synthetic lead** checkbox
defaults to enabled; electronic choir remains separately controllable from
the original prompt. No synthetic lead replacement or voice cloning happens.

Output PCM must be exactly canonical 44-byte RIFF WAV, mono/stereo PCM16,
at a supported matching rate. The dry file is limited to 20 MiB; the output
to 64 MiB to reduce phone-memory risk. This is in-memory, synchronous sample
alignment implemented with cooperative asynchronous chunks, not a streaming
DAW, automatic vocal tuning, stem separator or mastering tool. On
cancellation or changes to source/settings, existing mixed playback URLs are
revoked and the stale mix is invalidated, while the original dry file remains
available. It is never silently persisted in the encrypted workspace. Any future real vocal mixing must preserve an independent dry track, ask for separate consent, and report the consequences of output gain or filtering.

No voice data is saved to the project automatically, transmitted, stored in the public offline cache, or recorded through a microphone. Removing the voice from the tab revokes its local playback and re-download handles.

## Sample-aligned private WAV mix — Phase 3A

Source and tests: [vocal mixer](../web/studio-vocal-mix.js),
[adversarial PCM tests](../scripts/test-studio-vocal-mix.mjs). Real Chromium
acceptance verifies the end-to-end dry import → sample alignment → local
mix WAV export → original dry SHA-256 and byte-fidelity path.

## Independent acceptance and self-critique

Automated checks verify the fail-closed grammar, deterministic score generation, XML measure timing, true MIDI binary headers/drum channel, WAV PCM output, separation of synthetic from natural sounds, raw dry WAV byte fidelity and browser-origin privacy. Real mobile-width Chromium tests exercise the actual UI, synthetic playback, exports and dry voice import.

Those checks establish the **software workflow**. They are not independent human evidence of musical beauty, emotional hypnotic effect, accurate species calls, stage-quality opera, professional rap/popsong vocals or orchestral instrument realism.

Next phases remain: authorized high-quality multisampling/physical modeling, phonetic sung-word generation, lyric-to-score alignment, professional note editing, off-main-thread long-form rendering, automated alignment/onset measurement (rather than artist-entered offsets), multi-stem audio production, original user-vocal recording (optional consent), rights documentation, accessibility and real-person listening tests.

NEXUS's constitutional rule stays **A_out <= A_in**: this program never grants authority to publish creative work, impersonate real singers, train on private voice, authorize accounts or incur external music API charges.
