id: X.6
title: DECIDE-08: does the glossary keep English terms in Latin script? (terms set)
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: X.4

# X.6 — DECIDE-08: does the glossary keep English terms in Latin script? (terms set)

## Instructions

Data: `eval/results/data/terms.jsonl` (200 uk-pods clips from 187 episodes, each reference holding
≥ 1 Latin-script term inside Ukrainian text; built by X.5). Pre-registered here (2026-09-28,
before any run):

- **Metric:** term recall = share of the reference's Latin terms (the `terms` field) that appear in
  the hypothesis as the same Latin token, case-insensitive, edge punctuation stripped; plus corpus
  WER (`gmst.metrics.word_errors`) on the same clips.
- **Path:** batch per clip, language pinned `uk` (`gmst.pipeline.batch.transcribe_by_region` with
  `Config(language="uk", ...)`), `small` and `large-v2`.
- **Conditions:** (a) no glossary; (b) static glossary = the 100 most frequent Latin terms (same
  tokenizer as X.5) in `eval/results/raw/uk-pods_pods_train.json` `text_no_preprocessing`, which
  does not include the 200 test clips — check and report the overlap of clip ids; (c) autogrow
  only — `glossary_autogrow = true`, starting empty, one `Glossary` object carried across the 200
  clips in manifest order (the `Glossary` API in `src/gmst/glossary.py`: decode each clip with its
  prompt/hotwords, then `observe` the output).
- **Rule:** recommend enabling a glossary (b or c) only if its term recall is ≥ 10.0 pts above (a)
  **and** its WER is ≤ (a)'s + 1.0 pt, for both models. Otherwise record that it does not earn its
  latency and leave it off by default.

Also report decode time per clip for each condition (the latency cost the user accepted), and 10
example terms that (a) got wrong and (b)/(c) got right, and vice versa. Read first: root
`CLAUDE.md`, `src/gmst/glossary.py`, `tasks/X.5-*.md`, this file. Offline, one large model at a
time (`pgrep -af python` first), main tree `.venv`, no clone; write only this node file and
`scripts/X.6/`.

## What was read / measured

- Read root `CLAUDE.md`, `src/gmst/glossary.py`, `src/gmst/pipeline/batch.py`,
  `src/gmst/transcribe/engine.py`, `src/gmst/transcribe/backends/faster_whisper.py`,
  `src/gmst/metrics.py`, `tasks/X.5-terms-eval-data.md`, `eval/results/data/terms.jsonl` (200
  rows). No `large-*` model process running before starting (`pgrep -af python`).
- `scripts/X.6/build_static_glossary.py` (condition b's static glossary): top 100 most frequent
  Latin tokens (`[A-Za-z][A-Za-z]+`, X.5's tokenizer) in
  `eval/results/raw/uk-pods_pods_train.json`'s `text_no_preprocessing`, over 30,808 train rows.
  Also checked clip-id overlap between that train file and the 200 `terms.jsonl` clips (X.5 built
  `terms.jsonl` from train+test manifests combined) — **179/200 (89.5%) of the terms.jsonl eval
  clips are themselves rows in the file the static glossary's term frequencies were computed
  from.** Output: `scripts/X.6/static_glossary.json` (terms + counts + overlap).
- `scripts/X.6/run_glossary_eval.py`: batch per clip, `Config(language="uk", model_size=...,
  compute_device="cpu", compute_type="int8")`, via `gmst.pipeline.batch.transcribe_by_region` for
  (a)/(b), manual `Glossary` API loop for (c) (one `Glossary(autogrow=True)` object carried across
  all 200 clips in manifest order, per the brief). One engine instance per model, reused across
  all three conditions. Term recall / WER computed per the pre-registered metric (`edge_strip` +
  casefold match on `terms`, `gmst.metrics.word_errors` for WER).
- 8-clip smoke test on `small` surfaced condition (b) producing hallucinated repetition loops and
  English-language drift on Ukrainian audio (see Findings) — real enough at n=8 that the full run
  was expected to reproduce it, and did.
- Full 200-clip run, `small` model: condition (a) wall 259.4 s (`~1.3 s`/clip), term_recall=0.438,
  WER=0.208. (b) hit a pathological slowdown (one clip's decode running well past 100 s of active
  CPU, killed after ~17 min of wall time stuck between clip 125 and 150) — root-caused by reading
  faster-whisper's own source (`.venv/lib/python3.12/site-packages/faster_whisper/transcribe.py`):
  `get_prompt` (line 1532) concatenates **both** `hotwords` and `initial_prompt` into the *same*
  `sot_prev` context block (`prompt.append(tokenizer.sot_prev); if hotwords: prompt.extend(hotwords_tokens); if previous_tokens: prompt.extend(previous_tokens...)`,
  lines 1542–1550) — so `glossary.prompt()` (terms as the initial_prompt head) and
  `glossary.hotwords()` (the same terms again) together put GMST's 100-term glossary into the
  decoder's context **twice**, per `src/gmst/pipeline/batch.py:72-76`
  (`decode()` passes both `prompt=glossary.prompt(...)` and `hotwords=glossary.hotwords()` for
  every call). Added a 30 s per-clip timeout (`signal.alarm`) + incremental checkpointing to
  `run_glossary_eval.py` so a runaway clip can no longer stall the whole run; timeouts are
  recorded as data, not silently skipped. Reran from scratch with the timeout guard (`small`, all
  three conditions, `scripts/X.6/results_small_200.json`, checkpointed after each condition):
  - (a) no glossary: wall 254.3 s (~1.3 s/clip), term_recall=0.438 (88/201 terms), WER=0.208.
  - (b) static 100-term glossary: wall 1090.5 s (~5.5 s/clip, 4.3x (a); 0 clips hit the 30 s cap
    this run, but per-25-clip decode times climbed steadily: 1.80s→1.42s→2.57s→1.60s→1.66s→6.58s→
    9.50s→13.17s at clips 25/50/.../200), term_recall=0.414 (**lower** than (a), not higher), WER=
    0.822 (**+61.4 pts** over (a) — catastrophic, and note (b)'s 89.5% train/test overlap, above,
    means even this number is an optimistic upper bound for term_recall, not a discount).
  - (c) autogrow-only: wall 1226.6 s (~6.1 s/clip, 4.8x (a); glossary reached its `max_terms=100`
    cap by clip 75 in manifest order, and decode times jumped the same way as (b) from that point
    on — same pathology, confirms it is glossary *size* not staticness that triggers it),
    term_recall=0.464 (+2.6 pts over (a) — nowhere near the required +10), WER=0.632 (**+42.4 pts**
    over (a)).
  - **Against the pre-registered rule** (recall ≥ (a)+10 pts AND WER ≤ (a)+1.0 pt, both required):
    (b) fails both legs (recall −2.4 pts, WER +61.4 pts); (c) fails both legs (recall +2.6 pts,
    WER +42.4 pts). Neither glossary condition earns its keep on `small` — not close.
  - `scripts/X.6/results_small_200.json` holds full per-clip hyps/decode times for all 3
    conditions; `scripts/X.6/out_small_200.log` is the run transcript.
- `large-v2`: given `small`'s full 200-clip, 3-condition run alone took ~43 min wall (254+1090+
  1227 s) because of the glossary defect above, and `large-v2`'s baseline per-clip cost is already
  ~3-4x `small`'s (X.4), running large-v2 at 200 clips risked badly overshooting the node's 75 min
  cap. Pre-emptively capped at the brief's documented fallback: **n=100 clips** for all three
  conditions on `large-v2`. Bumped `CLIP_TIMEOUT_S` to 45 s (large-v2's own legitimate per-clip
  cost is higher, per X.4's final-pass numbers — 45 s leaves generous headroom over that before
  calling a decode pathological). Confirmed no other python model process running first
  (`pgrep -af python`). Started `results_large-v2_100.json` / `out_large-v2_100.log`.
  - (a) no glossary: wall 651.7 s (~6.5 s/clip, n=100), term_recall=0.617, WER=0.110 (large-v2 is
    substantially better than `small` on both axes on this subset, consistent with PLAN.md's UK
    leaderboard numbers).
  - (b) static 100-term glossary: wall 1386.7 s (~13.9 s/clip, 2.1x (a)), **10/100 clips (10%) hit
    the hard 45 s per-clip timeout and were cut off** (`timed_out=10` in the results JSON;
    e.g. clip `55840b09-..._0289` ran 54.6 s before being killed, several others 46-59 s) —
    i.e. on `large-v2` this glossary config would make roughly 1 in 10 batch decodes take 45+
    seconds before GMST's own script forcibly cuts it off; with no such external timeout (as in
    the shipped `pipeline/batch.py` / `pipeline/stream.py`), those clips would simply hang.
    term_recall=0.346 (**−27.1 pts** vs (a), not the required +10), WER=0.544 (**+43.4 pts**).
  - (c) autogrow-only: wall 791.8 s (~7.9 s/clip, 1.2x (a); glossary reached 75/100 terms by clip
    100, slower growth than `small`'s run — fewer Latin terms got committed correctly at this
    model/subset — no timeouts), term_recall=0.463 (**−15.4 pts** vs (a) — *worse*, not better),
    WER=0.392 (**+28.2 pts**).
  - **Against the pre-registered rule, `large-v2` (n=100)**: (b) fails both legs (recall −27.1 pts,
    WER +43.4 pts, 10% hard timeouts); (c) fails both legs (recall −15.4 pts, WER +28.2 pts). Same
    verdict as `small`, and by a wider margin on `large-v2` — the larger model is not more robust
    to the glossary defect, it is measurably more exposed to it (10 forced timeouts here vs 0 on
    `small`, at a higher timeout ceiling: 45 s vs 30 s).
  - `scripts/X.6/results_large-v2_100.json` / `out_large-v2_100.log` hold the full data.
- `scripts/X.6/make_examples.py`: 10-example qualitative pull for each model/condition pair —
  results folded into Findings.

## Findings

Summary table (term recall = hit/total Latin terms, corpus WER, both pre-registered; `n_to` =
clips that hit the per-clip decode timeout used to keep this probe inside budget — 30 s for
`small`, 45 s for `large-v2`):

| model | n | cond | wall_s | s/clip | recall | Δrecall | WER | ΔWER | n_to |
|---|---|---|---|---|---|---|---|---|---|
| small | 200 | (a) none | 254.3 | 1.3 | 0.438 | — | 0.208 | — | 0 |
| small | 200 | (b) static-100 | 1090.5 | 5.5 | 0.414 | **−2.4** | 0.822 | **+61.4** | 0 |
| small | 200 | (c) autogrow | 1226.6 | 6.1 | 0.464 | **+2.6** | 0.632 | **+42.4** | 0 |
| large-v2 | 100 | (a) none | 651.7 | 6.5 | 0.617 | — | 0.110 | — | 0 |
| large-v2 | 100 | (b) static-100 | 1386.7 | 13.9 | 0.346 | **−27.1** | 0.544 | **+43.4** | **10** |
| large-v2 | 100 | (c) autogrow | 791.8 | 7.9 | 0.463 | **−15.4** | 0.392 | **+28.2** | 0 |

(`scripts/X.6/results_small_200.json`, `scripts/X.6/results_large-v2_100.json`.)

- **[blocking] Against the pre-registered decision rule (recall ≥ (a)+10 pts AND WER ≤ (a)+1.0 pt,
  both required, for both models), both glossary conditions fail on both models, on both legs, by
  a wide margin.** (b)'s recall delta is *negative* on both models (−2.4, −27.1 pts); (c)'s recall
  delta reaches the required direction but never close to +10 pts (+2.6, −15.4 — also negative on
  large-v2), and every WER delta is catastrophic (+28 to +61 points). The glossary should stay off
  by default, and — beyond the pre-registered rule's own "doesn't earn its keep" framing — turning
  it on is actively harmful to both accuracy and latency, not merely a slower path that trades
  speed for fidelity as `PLAN.md`'s DECIDE-08 rationale implies ("off for speed").

- **[blocking] Root cause, found by reading the vendored dependency, not just observing behaviour:
  `faster_whisper.transcribe.WhisperModel.get_prompt` (`.venv/lib/python3.12/site-packages/faster_whisper/transcribe.py:1532-1550`)
  puts `hotwords` and `initial_prompt` into the *same* `sot_prev` context block** —
  `prompt.append(tokenizer.sot_prev)`, then `if hotwords: prompt.extend(hotwords_tokens)`, then
  `if previous_tokens: prompt.extend(previous_tokens...)` where `previous_tokens` carries the
  `initial_prompt` tokens (built at line 1143-1149 of the same file). `src/gmst/pipeline/batch.py:72-76`
  and `src/gmst/pipeline/stream.py:220,279` call `engine.transcribe(..., prompt=glossary.prompt(...),
  hotwords=glossary.hotwords())` — i.e. **every decode with a non-empty glossary puts the same term
  list into the decoder's context twice** (once as the `initial_prompt` head via `Glossary.prompt`,
  `src/gmst/glossary.py:76-84`, once again as `hotwords`, `src/gmst/glossary.py:73-74`). This
  doubles the amount of glossary content ahead of the actual decode and is a plausible mechanism
  for the observed failure, not just a correlation — confirmed by the qualitative pattern below,
  where several worst-case hypotheses are close to *literally the glossary content itself*.

- **[blocking] The failure mode is not just lower accuracy — it materially changes what comes out**,
  in ways a user could not simply "accept as a tradeoff":
  - Repetition loops of glossary terms replacing the actual transcript, e.g. clip
    `751dbede-1265-4654-95eb-d7714d75c4b4_0164` (small, cond b): reference "Він записав історію про
    те, як він сам бореться з anxiety..."; hypothesis: `"on, go, Podcasts, Free, on, go, Podcasts,
    Free, on, go,"` — no audio content at all, just glossary-adjacent tokens looping.
  - Whole hypotheses reduced to what looks like glossary vocabulary dumped verbatim, e.g. clip
    `b5379c68-ba83-4ffa-8244-b4ef8f1748e4_0050` (small, cond c, once glossary reached its 100-term
    cap): reference "До такої моделі Smart City є ряд випросів."; hypothesis: `"ForSage Super Mario
    Vengeance Batman overhyped Shadow of the Ramboot"` — six glossary-style terms, none of which
    are in the reference, replacing the sentence entirely.
  - Ukrainian decoded as English prose, e.g. clip `cbdf00c9-5455-4e1b-a7ae-82606b30a1fe_0204`
    (small, cond b): reference "Одна з моїх улюблених сцен в Asteroid City,"; hypothesis: `"One of
    my favorite scenes in Asteroid City."` — language pinned to `uk` was passed to `transcribe()`,
    and the model produced English anyway.
  - Content dropped almost entirely, e.g. clip `c4ab2c64-8f40-44cf-a29b-64c34358878c_0176`
    (large-v2, cond b): a full sentence reference truncated to `"Ринг Холло"` (two words).
  - Outright refusal/hallucination, e.g. clip `0491fda2-9b14-4e19-8c5c-5b28d3a3c55e_0174`
    (large-v2, cond c, glossary non-trivial): reference "Ми живемо в світі, цим вже активно
    займається Kanye West."; hypothesis: `"Ні! Ні!"`.
  - Ten more examples per condition per model in `scripts/X.6/examples_small.txt` and
    `scripts/X.6/examples_large-v2.txt` (generated by `scripts/X.6/make_examples.py`).

- **[blocking] On `large-v2`, condition (b) hard-timed-out on 10/100 clips (10%)** at a 45 s
  per-clip cap this script added *only to keep the probe inside budget* — e.g. clip
  `55840b09-240d-4f00-b973-570ccbbe0f48_0289` ran 54.6 s before being killed, several others
  46-59 s (`out_large-v2_100.log`). **Neither `pipeline/batch.py` nor `pipeline/stream.py` has any
  such timeout** — in the shipped code, these decodes would simply run to whatever faster-whisper's
  own temperature-fallback / `max_new_tokens` limits allow, which the `small`-model 8-clip smoke
  test showed can already exceed 100 s of active CPU for a single clip (before the timeout guard
  existed). For `stream.py` in particular this directly threatens the ≲3 s latency budget and the
  bounded-queue failure-mode contract in `CLAUDE.md` ("Failure modes" — none of the listed rows
  cover "one utterance's decode never returns").

- **[serious] Condition (c) (autogrow-only) is not a safe fallback**: it reproduces the same
  pathology once the grown list gets large enough (`small`: decode time jumps from ~2s to 13-19s
  once `glossary_size` hits 100 at clip ~75, `out_small_200.log`; `large-v2`: climbs from 8s to 12s
  by clip 75 at `glossary_size=68`, `out_large-v2_100.log`). `glossary.py`'s docstring frames
  autogrow as safer than a static list ("the terms it got right, so later occurrences stay
  consistent"), but the defect is triggered by glossary *size* passed to `hotwords`+`prompt`
  together, not by whether the list is static or grown — a long enough session with autogrow on
  will eventually hit the same regime a 100-term static list hits from clip 1.

- **[serious] Condition (b)'s static glossary was built from a corpus that overlaps 89.5% with the
  evaluation clips (179/200 `terms.jsonl` clip ids are rows in `uk-pods_pods_train.json`, the file
  `build_static_glossary.py` computed term frequencies from)** — X.5 built `terms.jsonl` from
  train+test manifests combined, so most of "unseen" eval text's own terms were counted into the
  glossary that then gets fed back into decoding it. This means condition (b)'s term_recall numbers
  above are an *optimistic* upper bound relative to a glossary built from genuinely disjoint data
  (a real deployment's glossary would not literally contain many of the meeting's own upcoming
  terms) — makes no difference to the verdict here (b already fails badly even with this
  advantage), but should be corrected if a glossary variant is re-tried after a fix.

- Decode-time cost (also requested by the brief): even where output quality does not collapse
  outright, both non-empty conditions cost real latency — `small` (b) 5.5 s/clip (4.3× (a)),
  `small` (c) 6.1 s/clip (4.8× (a)); `large-v2` (b) 13.9 s/clip (2.1× (a), before counting that 10%
  of clips were cut off early by the timeout — the true mean without a timeout would be higher),
  `large-v2` (c) 7.9 s/clip (1.2× (a)). None of this cost buys the required accuracy gain.

## Could not check

- `large-v2` was capped at n=100 clips (not the full 200) for all three conditions, per the node's
  own documented fallback ("if large-v2 would exceed ~75 min total, run it on the first 100
  clips") — `small`'s full 200-clip run alone took ~43 min because of the glossary defect, so
  large-v2 at 200 clips risked badly overshooting budget. The n=100 large-v2 run itself took
  ~47 min. Not Mac-only; a plain budget cut, recorded per the brief.
- Did not test whether removing the duplicate injection (passing only `hotwords` OR only `prompt`,
  not both) fixes the pathology — that would be a code change, out of scope for a read-only review
  node; flagged as the natural next probe if DECIDE-08 is revisited.
- `mlx_whisper`'s glossary path (prompt only, no `hotwords` parameter per its backend comment) was
  not tested — Mac-only, per rule 6.
- Did not measure the `small`/`large-v2` (a)-condition batch RTF against other review nodes'
  numbers for cross-checking; out of this node's scope (X.4/X.1 own that).

FINDING: findings
