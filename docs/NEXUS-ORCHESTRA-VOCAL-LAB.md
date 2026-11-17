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

The optional simultaneous backing audition starts two separate audio players at normal playback speed. It is *not sample-accurately synchronized*, does not export a combined vocal mix, and does not change the original recorded bytes. Any future real vocal mixing must preserve an independent dry track, ask for separate consent, and report the consequences of output gain or filtering.

No voice data is saved to the project automatically, transmitted, stored in the public offline cache, or recorded through a microphone. Removing the voice from the tab revokes its local playback and re-download handles.

## Independent acceptance and self-critique

Automated checks verify the fail-closed grammar, deterministic score generation, XML measure timing, true MIDI binary headers/drum channel, WAV PCM output, separation of synthetic from natural sounds, raw dry WAV byte fidelity and browser-origin privacy. Real mobile-width Chromium tests exercise the actual UI, synthetic playback, exports and dry voice import.

Those checks establish the **software workflow**. They are not independent human evidence of musical beauty, emotional hypnotic effect, accurate species calls, stage-quality opera, professional rap/popsong vocals or orchestral instrument realism.

Next phases remain: authorized high-quality multisampling/physical modeling, phonetic sung-word generation, lyric-to-score alignment, professional note editing, off-main-thread long-form rendering, sample-accurate multitrack vocal alignment, non-destructive voice mixing, original user-vocal recording (optional consent), rights documentation, accessibility and real-person listening tests.

NEXUS's constitutional rule stays **A_out <= A_in**: this program never grants authority to publish creative work, impersonate real singers, train on private voice, authorize accounts or incur external music API charges.
