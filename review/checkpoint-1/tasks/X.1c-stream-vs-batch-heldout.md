id: X.1c
title: EVID-01 after F.15, on the original clips and on unseen clips
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: F.15

# X.1c — EVID-01 after F.15, on the original clips and on unseen clips

## Instructions

X.1b.1 iterated on X.1's 20+20 clips, so they are no longer a clean test. Pre-registered here
(2026-09-28, before running): EVID-01's rule, unchanged — stream ≤ batch + 3.0 pts on en and uk
with `small`, contradicted pushes ≤ 10 % — evaluated on **(a)** X.1's clips (manifest rows 0–19)
and **(b)** unseen clips (manifest rows 20–39 of `en.jsonl` / `uk.jsonl`); the verdict is (b)'s.
Run each stream **twice** and report both (Ukrainian decoding was non-deterministic under F.14).
Then `large-v2` on (b) en and uk, once, within ~60 min. Copy `scripts/X.1/run_wer.py` to
`scripts/X.1c/` adding only a row-offset option and output paths; save full outputs. Read first:
root `CLAUDE.md`, `review/checkpoint-1/PLAN.md`, `tasks/V1-*.md`, `tasks/X.1*.md`, this file.
Offline, one large model at a time (`pgrep -af python` first), main tree `.venv`, no clone; write
only this node file and `scripts/X.1c/`.

## What was read / measured

Read: root `CLAUDE.md`; `review/checkpoint-1/PLAN.md` rules 1-8; `tasks/V1-evidence-plan.md`
(pre-registered EVID-01 rule, unchanged: **holds** if corpus stream WER ≤ batch WER + 3.0 pts on en
and uk with `small`, and contradicted-push share ≤ 10%); `tasks/X.1-*.md` (pre-F.14: en +4.32pts,
uk +3.50pts, both fail; 0% contradicted); `tasks/X.1b-*.md` (post-F.14: en 0.00pts pass, uk
**+21.67pts** — hallucinated tokens "Zum2i"/"осьoof1"; large-v2 en run for X.1b finished after that
node's handback — batch 1.68%, stream 2.88%, i.e. +1.20pts, pass — read from
`scripts/X.1b/large-v2_results.json`, not this node's own measurement, not used for X.1c's verdict);
`tasks/X.1b.1-*.md` (diagnosed F.14: dropping the anchor from the prompt makes uk decoding
non-deterministic/hallucination-prone; F.15 = variant "E+H" — gated time cut by resemblance + 5-word
text/n-gram history check against the anchor-inclusive prompt — measured uk 25.17% both runs on
X.1's original clips, en 22 edits/417, diagnosis only, same clips as X.1); `tasks/F.14-*.md`,
`tasks/F.15-*.md` (fix under test here). Confirmed F.15 is present in the tree at 441ea26:
`grep -n "_history\|_resembles" src/gmst/reconcile.py` shows `_resembles` (reconcile.py:56),
`self._history` (reconcile.py:64, updated on push/flush/absorb/reset) — matches F.15's description.

Wrote `scripts/X.1c/run_wer.py` (copy of `scripts/X.1/run_wer.py`, en/uk only, adds `offset:tag`
positional args to select manifest rows `[offset:offset+20)` and a `stream_runs` count to repeat
the stream decode N times per set; writes `<model>_<tag>_results.json` per offset and
`<model>_all_results.json` combined). Wrote `scripts/X.1c/clips.txt` (80 lines: set, tag, id, wav
path — tag `a` = rows 0-19, tag `b` = rows 20-39, en and uk) before any run, matching X.1's
methodology. `pgrep -af python` before starting: no Python process loading a model (only KDE
plasmoid helpers and an unrelated zsh loop waiting on a download, same as noted in X.1b).

Started `small` run, both tags, stream x2 each, in background:
`HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1c/run_wer.py small 2 0:a 20:b`
→ `scripts/X.1c/small_run.log`. `small` run completed, ~40 min wall (started 20:16, finished before
20:57), no other Python model-loading process running throughout (`pgrep -af python` checked before
start and again after completion — only KDE plasmoids and an unrelated zsh loop waiting on a
download). Results: `scripts/X.1c/small_a_results.json`, `scripts/X.1c/small_b_results.json`.
Starting `large-v2` on tag `b` only (en, uk), stream x1, per the brief's budget.
`large-v2` run completed (`scripts/X.1c/large-v2_run.log`, `scripts/X.1c/large-v2_b_results.json`),
~40 min wall (batch 126.9+109.9=236.8s, stream 1586.5+565.6=2152.1s, total ≈2389s), within the ~60
min budget; no other Python model-loading process running throughout (`pgrep -af python` checked
immediately before the run started).

## Findings

Pre-registered rule (V1, EVID-01, unchanged): **holds** if corpus stream WER ≤ batch WER + 3.0 pts
on en and uk with `small`, and contradicted-push share ≤ 10%; evaluated on (a) X.1's original
clips (manifest rows 0-19) and (b) unseen clips (rows 20-39); **the verdict is (b)'s.**

**`small`, set (a) — X.1's original clips (`scripts/X.1c/small_a_results.json`):**

| set | mode | WER | edits/ref | gap vs batch |
|---|---|---|---|---|
| en | batch | 2.64% | 11/417 | — |
| en | stream rep0 | 6.47% | 27/417 | **+3.83 pts (fails)** |
| en | stream rep1 | 4.80% | 20/417 | +2.16 pts (passes) |
| uk | batch | 23.78% | 34/143 | — |
| uk | stream (both reps, identical) | 25.17% | 36/143 | +1.39 pts (passes) |

en is now **non-deterministic across the two runs on this node's own machine and code**, one run
failing the 3.0-pt margin and one passing it — this reproduces X.1b.1's uk finding for F.14
("Ukrainian decoding was non-deterministic") but shows it now also affects **English** post-F.15 on
this set, which X.1b.1's diagnosis (uk-only A/B table) did not check. uk matches X.1b.1's E+H
number for this exact clip set almost exactly (25.17% here and there, deterministic both times) —
consistent, but that consistency turns out to be an artifact of testing on the clips F.15 was tuned
against (see set (b) below).

**`small`, set (b) — unseen clips, manifest rows 20-39 (`scripts/X.1c/small_b_results.json`), the
deciding set:**

| set | mode | WER | edits/ref | gap vs batch |
|---|---|---|---|---|
| en | batch | 3.51% | 11/313 | — |
| en | stream rep0 | 5.11% | 16/313 | +1.60 pts (passes) |
| en | stream rep1 | 5.43% | 17/313 | +1.92 pts (passes) |
| uk | batch | 14.29% | 18/126 | — |
| uk | stream (both reps, identical) | **79.37%** | 100/126 | **+65.08 pts (fails, ~22× the 3.0-pt bar)** |

**[blocking] On unseen Ukrainian audio, F.15's streaming path is catastrophically worse than batch —
deterministically — and the failure mode is not the "contradicted push" F.8/F.15's machinery
tracks.** `small_b_results.json`, uk, `contradicted=0/93` both reps, yet the committed output
repeats whole clauses verbatim, non-adjacently, several times. Example (`full_out`, both reps
byte-identical): batch's correct hyp for clip `uk-988` is `" Розпочали рити котлован"` (3 words);
the concatenated stream output contains the extended clause **"Розпочали рити котлован Цей сервіс
дозволить(и) тепер Плотити через смартфон..." at least five times** across the transcript, e.g.:
`...Розпочали рити котлован Цей сервіс дозволить тепер Плотити через смартфон, а не через цей касом
Інших пояснень немає Розпочали рити котлован Цей сервіс дозволить тепер Плотити через смартфон, а
не через цей касом Будь ласка!...` (immediate back-to-back repeat), then again later: `...Отребуно!
Скільки дурнів Сходило з тебе переможцями Розпочали рити котлован Цей сервіс дозволити тепер
Плотити через смартфон Розпочали рити котлован Цей сервіс дозволити тепер Плотити через смартфон
рити котлован Цей сервіс Плотити через смартфон Розпочали рити котлован Цей сервіс дозволити тепер
через смартфон...` — the same ~8-word clause committed at least 5 times over a ~188-word output for
a 126-word reference. This is exactly the class of defect CLAUDE.md's reconciliation invariants
name ("a revised prefix is never re-committed"): F.15's de-duplication is a text/n-gram check
against only the last `_MAX_NGRAM = 5` committed words (`reconcile.py:46`, confirmed via
`grep _MAX_NGRAM src/gmst/reconcile.py`) — it catches an *immediately adjacent* repeat of ≤5 words
but not a ~8-word clause re-committed after other material has been committed in between, which is
what happens here. `_history` is capped at 5 words and does not detect longer-range repetition.

**`large-v2`, set (b) only, stream x1, per budget (`scripts/X.1c/large-v2_b_results.json`):**

| set | mode | WER | edits/ref | gap vs batch |
|---|---|---|---|---|
| en | batch | 2.24% | 7/313 | — |
| en | stream | **32.27%** | 101/313 | **+30.03 pts (fails, 10× the bar)** |
| uk | batch | 8.73% | 11/126 | — |
| uk | stream | 7.14% | 9/126 | **−1.59 pts (passes — stream better than batch)** |

**[blocking] `large-v2` inverts the pattern: on set (b), English is the language that fails
catastrophically, Ukrainian passes (even beats batch).** `large-v2_b_results.json`, en,
`contradicted=0/148`. The stream output contains a fabricated, audio-unrelated insertion —
`"...for the struggle. information visit www .FEMA .gov But do not suppose..."` (`.FEMA .gov` does
not appear anywhere in the reference or in any batch hyp for this set) — followed by a distinct,
repeating boilerplate hallucination, the literal token sequence `"End 1"` (and later `"End 2"`,
bare digits `1`/`2`/`3`/`4`) inserted after nearly every subsequent sentence for the rest of the
390-word transcript, e.g. `...I disparage gift which you possess... End 1 Her sea-going qualities
were excellent... End 1 It is founded on the acknowledged weakness... End 1 Of what Mrs. Neverbend
had gone through... End 1 But it must be admitted... End 1 Success 2 3 4 Dead Master summoned
me...`. This is a Whisper decoder hallucination pattern (subtitle/footnote-numbering artifacts,
well documented for long-context streaming decode with a stale prompt), not a reconciliation
contradiction — `contradicted=0` again — so F.8/F.15's contradiction-tracking does not see this
failure mode at all.

**Contradicted-push share: 0% in every run measured in this node** (small a: 179/179, 98/98 both
langs both reps; small b: 147/147 en both reps, 93/93 uk both reps; large-v2 b: 148, 93) — F.8's
terminal-contradiction fix continues to hold cleanly; it is simply not the mechanism behind either
failure found here.

**Net against the pre-registered rule, decided by (b):** uk fails on `small` (+65.08 pts, deciding
model) and en fails on `large-v2` (+30.03 pts, reported per the brief). Both are far larger in
magnitude than any gap measured in X.1 (pre-fix, worst case +22.37 pts on mixed-inter) or X.1b
(post-F.14, uk +21.67 pts). **DECIDE-01 remains reopened, on stronger evidence than before:** F.15's
apparent close-to-passing numbers on set (a) — the very clips X.1b.1 iterated its A/B/E/E+H
variants against — do not generalize to unseen audio; the held-out set produces two independent,
deterministic, order-of-magnitude failures (uk/small: verbatim clause duplication past the 5-word
history window; en/large-v2: Whisper hallucination boilerplate), each ~10-22× over the 3.0-pt
margin, on clips this node's brief explicitly chose because the prior iteration had made the
original 20+20 "no longer a clean test."

## Could not check

- Could not attribute the `en`/small set (a) non-determinism (rep0 fails, rep1 passes) to a specific
  cause — only two reps were run per the brief; a longer run of reps was out of budget.
- Per-clip attribution inside the concatenated stream WER is not available (same limitation as
  X.1/X.1b — one corpus-level edit distance over the whole concatenation).
- `large-v2` was not run on set (a) (not asked for by the brief) and not on `mixed` (not asked for),
  so there is no large-v2 comparison point against X.1's/X.1b's large-v2 numbers on the same clips
  for set (b).
- Did not investigate further (e.g. varying `_MAX_NGRAM`, disabling the prompt, or bisecting which
  concatenated clip triggers the hallucination) — out of scope for an evidence node; this is
  material for a fix node.

FINDING: findings
