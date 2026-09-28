id: X.5
title: DECIDE-06: find public Ukrainian speech with English terms, and build a terms eval set
parent: X
stage: evidence
kind: task
agent: general-purpose
model: sonnet
effort: high
status: in-progress
depends-on: -

# X.5 — DECIDE-06: find public Ukrainian speech with English terms, and build a terms eval set

## Instructions

The user's meetings are *Ukrainian with English technical terms* (H1, 2026-09-28) and they cannot
supply recordings; they asked for public datasets. Read first: root `CLAUDE.md`, root `PLAN.md`
"Review decisions" (DECIDE-06, DECIDE-08), `review/checkpoint-1/PLAN.md`, this file. Set
`status: in-progress` before starting. **Rule 4 is amended for this node only (2026-09-28, the
user asked for a web search): network access and dataset downloads are allowed**, up to ~10 GB
total, into `eval/results/raw/` (git-ignored). Write only this node file, `scripts/X.5/` and new
files under `eval/results/`.

Candidates found by the orchestrator (verify each; search for more — IT/tech podcasts, conference
talks, YouTube with manual subtitles, anything with uk–en code-switching):
- `taras-sereda/uk-pods` (HF): 51 h, podcast "Вертіго" (film/media), CC-BY-NC-4.0, manifests
  `pods_train.json` / `pods_test.json` with `text` and `pred_text`; card examples keep "MCU",
  "retouch" in Latin script. **Provenance of `text` unknown.**
- `espnet/yodas2` `uk000` / `uk100` (HF): YouTube, CC BY 3.0; manual vs automatic subtitles per
  subset is unconfirmed.
- `Yehor/broadcast-speech-uk` (~300 h), `speech-uk/voice-of-america` (~390 h).

Pre-registered rule (fixed now, before any download):
- A source is **usable as reference** only if its transcripts are human-made (manual subtitles,
  human transcription, or human-corrected), established from its card, paper, repo, or by
  evidence in the data (e.g. `text` differing from `pred_text` in human-correction patterns).
  Whisper-generated references are rejected: scoring Whisper against Whisper is circular.
- A **terms set** is buildable if the usable sources yield **≥ 150 clips** whose reference contains
  ≥ 1 Latin-script token of ≥ 2 letters inside otherwise Ukrainian text, from **≥ 10 distinct
  speakers or episodes**. Otherwise record what exists and say so.

Deliverables: per candidate — size, licence, domain, provenance of transcripts (with the quote or
evidence), count of Latin-term clips in a sample; if the rule holds, a script
`scripts/X.5/build_terms_set.py` that writes `eval/results/data/terms/*.wav` (16 kHz mono) and
`eval/results/data/terms.jsonl` with `{id, wav, text, terms: [...]}`, and the counts. Do not run
any ASR model beyond `tiny` (for spot checks only). Offline rules otherwise unchanged; X.1 may be
loading models concurrently — keep CPU use modest.

## What was read / measured

- Root `CLAUDE.md`, `PLAN.md` lines 321-326 (DECIDE-06, DECIDE-08), `review/checkpoint-1/PLAN.md`
  (rules, scope), this node file, `eval/build_sets.py` (existing conventions: `RAW`/`OUT` layout,
  `_to_16k_mono`).
- HF dataset card READMEs fetched raw (`curl .../raw/main/README.md`) for all four candidates:
  `taras-sereda/uk-pods`, `espnet/yodas2`, `Yehor/broadcast-speech-uk`, `speech-uk/voice-of-america`
  (saved under `/tmp/readme_*.md`, not committed — reproducible via the URLs below).
- `espnet/yodas` card (v1, via WebFetch) for the `000`/`100` manual/automatic caption naming
  convention; confirmed the same `uk000`/`uk100` subset pair exists under `espnet/yodas2` via
  `https://huggingface.co/api/datasets/espnet/yodas2/tree/main/data`.
- `taras-sereda/uk-pods`: downloaded `pods_train.json` (30808 lines) + `pods_test.json` (3423
  lines) directly (`eval/results/raw/uk-pods_pods_{train,test}.json`), and one example clip
  (`example/e934c3e4-c37b-4607-98a8-22cdff933e4a_0266.wav`, 16 kHz mono PCM16, confirmed via
  `soundfile.info`). Ran a `uv run --with` offline `faster-whisper` **tiny** spot check on that one
  clip (`HF_HUB_OFFLINE=1`, cached model, no download) — matched the reference content, sanity-
  checking audio/text alignment.
- Wrote and ran a filter over both manifests (`text_no_preprocessing` field) counting clips with a
  Latin-script token (>=2 letters) embedded in a majority-Cyrillic line; see Findings for counts.
  Logic then folded into `review/checkpoint-1/scripts/X.5/build_terms_set.py`.
- Started downloading the full `clips.tar.gz` (5,241,232,164 bytes, confirmed via
  `Content-Length`) in the background to `eval/results/raw/uk-pods_clips.tar.gz` (~2.6-3.8 MB/s;
  the archive is not orderable/seekable by episode — a `tar -tzf` on a truncated prefix showed
  clip UUIDs interleaved, not grouped by episode, so a streamed partial extract would not have
  saved bandwidth over downloading the whole file). **Session ended before the download finished
  (~490 MB / 5.24 GB at last check) — `build_terms_set.py` was written and is ready but has not
  been run yet.** Resuming: check
  `ls -la eval/results/raw/uk-pods_clips.tar.gz` against 5241232164 bytes; if the `curl` (pid was
  125421, likely gone after session end — just re-run
  `curl -sL https://huggingface.co/datasets/taras-sereda/uk-pods/resolve/main/clips.tar.gz -o eval/results/raw/uk-pods_clips.tar.gz`)
  is done, run `uv run python review/checkpoint-1/scripts/X.5/build_terms_set.py` (needs
  `eval/results/raw/uk-pods_pods_{train,test}.json`, already present) and update this section +
  flip `status:` to `done`.
- `Yehor/broadcast-speech-uk` / `speech-uk/voice-of-america`: HF cards give no transcript
  provenance; traced the "ASR Corpus Creator" citation on the Voice-of-America Zenodo records
  (`zenodo.org/records/7404898`, `7404392`) to its own Zenodo page
  (`zenodo.org/record/7396705`) and read that page's raw HTML for its description.
- `espnet/yodas2` `uk000`: fetched 5 of the per-video text JSON shards under
  `data/uk000/text/00000000.json`..`00000004.json` (~700 KB each, text only, no audio pulled) and
  ran the same Latin-token filter for a sample count.

## Findings

Pre-registered rule (unchanged, quoted from this file): a source is usable as reference only if
its transcripts are human-made, established from card/paper/repo, **or** by evidence in the data
(e.g. `text` differing from `pred_text` in human-correction patterns); Whisper-generated
references are rejected. A terms set is buildable if usable sources yield >=150 clips with >=1
Latin-script token of >=2 letters inside otherwise-Ukrainian text, from >=10 distinct
speakers/episodes.

**`taras-sereda/uk-pods` — USABLE (evidence-in-the-data route).**
- 51.066 h, 34,231 clips, CC-BY-NC-4.0, domain: film/pop-culture podcast "Вертіго".
- The HF card documents no provenance for `text`/`pred_text` (matches CLAUDE.md's existing note:
  "Provenance of `text` unknown").
- Evidence in the data: the manifest carries four text fields per clip —
  `text_no_preprocessing` (original casing/punctuation), `text` and `text_normalized`
  (lowercased), and `pred_text` (an ASR model's own transcript of the same clip, scored against
  `text` via `wer`/`cer` fields it also ships). `text_no_preprocessing` keeps loanwords/brand names
  in correct Latin spelling — e.g. `"Навіть я вважаю, що Pixar вже не той."`,
  `"Тому, власне, місія Dreamcast..."`, `"Подкаст, який ми часто називаємо FilmSpotting."` — while
  `pred_text` on the *same clips* garbles or transliterates the same span into Cyrillic:
  `"голг"`/`"дауонлод"` for Google/Download, `"дрім кастсту"` for Dreamcast, `"сеаркхінг"` kept
  phonetic rather than corrected. That is exactly the ASR-vs-human asymmetry the rule asks for —
  an ASR pass does not reliably recover correctly-spelled OOV Latin proper nouns, a human
  transcriber (or corrector) does. Quotes and side-by-side pairs are reproducible via
  `build_terms_set.py`'s module docstring and the ad-hoc grep in "What was read".
  - Caveat: `text` (the field actually named `text`, used for ASR training) is a **lowercased and
    transliterated** derivative of `text_no_preprocessing` — e.g. `Google` → `гоогле`, `Pixar` →
    `пікар`, `HBO` → `хбо`, `Netflix` → `нетфлік` — and has *already lost all Latin script* (0/3423
    test-split clips have a Latin token in `text`, vs 102/3423 in `text_no_preprocessing`). Only
    `text_no_preprocessing` is usable as a terms reference; the script uses that field.
- Sample count (full train+test manifests, not just a sample): **1,062 candidate clips** with a
  Latin token (>=2 letters) inside a majority-Cyrillic line (>=10 Cyrillic letters, Latin letters
  <= Cyrillic letters, duration >=1.0 s), spanning **187 distinct episodes** (by the manifest's
  per-episode audio-UUID prefix). Comfortably clears 150 clips / 10 episodes on its own.
  Representative terms found: MCU, retouch, Lost, Nike, AirPods, Grand Budapest, Netflix, Google,
  Pixar, HBO, Disenchantment, Apple, DC, FilmSpotting, Dreamcast, PDF.
- **Not yet built**: `build_terms_set.py --target 200 --per-episode 6` (default args) is written
  and ready to select ~200 clips spread across episodes and extract them from the 5.24 GB
  `clips.tar.gz` (already 16 kHz mono PCM16 — no resampling needed), writing
  `eval/results/data/terms/*.wav` + `eval/results/data/terms.jsonl` (`{id, wav, text, terms}`).
  The `clips.tar.gz` download did not finish before this session ended (see "What was read /
  measured" for the resume command); the script itself was not run. The rule-holds conclusion
  below does not depend on this step — it's decided by the manifest-only candidate count (1,062
  clips / 187 episodes), which does not need the audio.

**`espnet/yodas2` `uk000` — LIKELY USABLE, not built into the set (secondary, scope reasons).**
- License CC-BY-3.0. The `espnet/yodas` (v1) card states verbatim: "We distinguish manual caption
  subset and automatic caption subset by the first digit in each shard's name. The first digit is
  0 if it contains manual captions, 1 if it contains automatic captions." `yodas2`'s own card says
  it "provides the same dataset as espnet/yodas ... but ... formatted in long-form" (same
  underlying labels), and its `data/` tree contains the same `uk000`/`uk100` pair — so `uk000` is
  documented (card route, one hop away) as manual/human-captioned YouTube subtitles.
  Domain: mixed YouTube (news/broadcast in the sample pulled, not IT-specific).
- Sample count: of 5 of the ~many per-video text shards under `data/uk000/text/` (23,842
  utterances, 78 distinct videos), **252 utterances** had a Latin token in a majority-Cyrillic
  line (~1% rate, lower than uk-pods' ~3%) — e.g. COVID, MEDAIR, Erasmus+, Zoom, Patriot. This
  alone, scaled, would also likely clear 150/10, but was not built into `terms.jsonl` — the X.5
  rule was already satisfied by uk-pods alone, and pulling yodas2 audio (per-video, not
  per-clip — needs cutting from `audio/` shards by the utterance timestamps encoded in each
  utterance key) was out of scope for this pass. **Caveat found in the sample**: at least one
  video's utterances were plainly Russian, not Ukrainian (e.g. "MIM-104 Patriot... используемый
  армией США..." — "используемый" is Russian, not Ukrainian) despite being filed under `uk000`;
  the `uk000` language tag is per-channel/video metadata, not verified per-utterance, so a real
  build from this source would need a language filter pass GMST doesn't have language-checked yet.

**`Yehor/broadcast-speech-uk` and `speech-uk/voice-of-america` — REJECTED (ASR-generated).**
- Neither HF card states provenance directly. Both are attributed (VOA's own Zenodo records,
  `zenodo.org/records/7404898` / `7404392`, title "Voice of America: Ukrainian ASR Dataset of
  Broadcast Speech") to the "ASR Corpus Creator" tool
  (`zenodo.org/record/7396705`, by the same author, Yehor Smoliakov). That tool's own Zenodo page
  states verbatim: *"This app is intended to automatically create a corpus for ASR systems using
  pseudo-labeling ... Export labeled data using a console whisper, wav2vec2, or NeMo as an ASR
  backend."* No mention of human transcription, correction or verification anywhere on that page
  (checked by substring count: 0 occurrences of "human"/"manual"). This is a textbook case of the
  rule's own exclusion: "Whisper-generated references are rejected: scoring Whisper against
  Whisper is circular" — Whisper is explicitly one of the three listed backends.
  `Yehor/broadcast-speech-uk` is not itself linked to a Zenodo record in its HF card, so its
  pipeline is inferred rather than directly confirmed: same author/initiative
  ("Speech-UK initiative and Yehor Smoliakov"), same undocumented `audio`/`transcription`/
  `duration` schema, no manual-transcription claim anywhere found (HF card, GitHub
  `egorsmkv/speech-recognition-uk` README, web search) — treated as REJECTED on the same basis,
  flagged as inferred-not-confirmed.

- [holds] The terms-set rule holds: `taras-sereda/uk-pods` alone yields 1,062 candidate clips
  (from its `text_no_preprocessing` manifest field — audio not required to count this) from 187
  distinct episodes, both far above the 150-clip / 10-episode thresholds, on a source whose
  Latin-term preservation is supported by in-data evidence (not merely an unverified card claim).
  **The audio extraction into `eval/results/data/terms/*.wav` + `terms.jsonl` itself was not
  completed this session** (clips.tar.gz download unfinished at session end) — the rule's
  "buildable" clause is satisfied on the manifest evidence, but the actual deliverable files do
  not exist yet. `build_terms_set.py` is ready to produce them as soon as the archive finishes
  downloading.

## Could not check

- Did not independently reproduce `taras-sereda/uk-pods`'s original transcript pipeline (no paper
  or repo beyond the HF card was found) — the provenance conclusion rests entirely on the
  text/pred_text asymmetry described above (data evidence), not on a documented human-transcription
  claim; this is the "established... by evidence in the data" branch of the rule, the weaker of
  the two branches, and the card itself is explicit that it doesn't say how `text` was made.
  A stronger form of this check (e.g. contacting the dataset author, or diffing against the
  original podcast's published subtitles if any exist) was out of scope.
- Did not confirm `Yehor/broadcast-speech-uk`'s pipeline directly (no Zenodo/paper link found in
  its HF card) — rejection is by inference from the sibling VOA dataset's confirmed pipeline and
  shared authorship/schema, not a first-hand citation for that dataset specifically.
- Did not download or scan `espnet/yodas2` `uk100` (the automatic-caption sibling of `uk000`) or
  more than 5 of `uk000`'s text shards — the 5-shard sample was enough to show the source is
  plausible but not to give an exact full-corpus count; not needed since uk-pods alone clears the
  rule.
- Did not attempt NeMo/Whisper-based per-utterance language-ID on the yodas2 `uk000` sample to
  quantify the Russian-contamination rate found in one spot-checked video — flagged as a caveat
  for a future pass on that source, not resolved here.

FINDING: recorded
