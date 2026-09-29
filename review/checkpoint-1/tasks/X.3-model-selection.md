id: X.3
title: EVID-03: model selection on the full cleaned CV10 uk set
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: F.2

# X.3 — EVID-03: model selection on the full cleaned CV10 uk set

## Instructions

After F.2's harness fixes: build the full cleaned-CV10 `uk` set (3204) and a 500-clip LibriSpeech test-clean `en` set, language pinned, `gmst-batch` path. Candidates `large-v2`, `large-v3`; ask the user before downloading `large-v3-turbo` / `Yehor/whisper-large-v3-turbo-quantized-uk`. Report corpus WER with bootstrap CIs and pairwise paired-bootstrap CIs. Expect hours per model on CPU: run overnight, one model at a time, resumable.

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.3/`. Write the clip list to `scripts/X.3/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

**Amended 2026-09-28 (user, before any X.3 run):** scope is **800** cleaned-CV10 `uk` clips (first
800 in a fixed seed-0 shuffle, written to `scripts/X.3/clips.txt` first) and the same 500 `en`
clips, candidates `large-v2`, `large-v3`, `large-v3-turbo`, `Yehor/whisper-large-v3-turbo-quantized-uk`
— downloads approved for the two turbo models (faster-whisper maps `large-v3-turbo` to
`mobiuslabsgmbh/faster-whisper-large-v3-turbo`, already partly cached; check whether the turbo-uk
repo is CTranslate2-loadable, and convert with `ct2-transformers-converter` into
`eval/results/models/` if it is not). Per R5 this resolves large-v2 vs large-v3 (~73 paired clips)
and large-v3 vs turbo (~761) but **not** turbo-uk vs large-v2 (~2,893): report that pair's CI
as-is, with no ranking claimed unless it excludes 0. The pre-registered rule is otherwise
unchanged. Runs after X.1 and X.4 (one large model at a time); overnight.

## What was read / measured

Read `V1-evidence-plan.md` (EVID-03 rule), `PLAN.md` rules 1-8, `eval/run_eval.py` (whole file),
`eval/build_sets.py` (whole file), `src/gmst/pipeline/batch.py:66-102` (`transcribe_by_region`,
language-pinned vs per-region LID), `src/gmst/config.py:30-35,101-186` (language field). Confirmed
X.1 and X.4 are `status: done` before starting (dependency order in the amendment). Confirmed no
other large-`*` model was loaded machine-wide before each run (`pgrep -af python`; another agent's
`X.5/build_terms_set.py` and a source-editing `F.18` process were running concurrently but load no
ASR model).

Built `scripts/X.3/build_uk800_en500.py` (reuses `eval/build_sets.py`'s `_load_uk`/`_load_en`/
`_write_pure` verbatim, seed=0, n=800/500) → wrote `eval/results/data/uk800.jsonl` (800),
`eval/results/data/en500.jsonl` (500), `eval/results/data/uk800/*.wav`, `eval/results/data/en500/*.wav`,
and `scripts/X.3/clips.txt` (the 1300 ids, uk800 then en500, in shuffle order) — none of these
existed before this node ran; `eval/results/data/en.jsonl`/`uk.jsonl` (the 60-clip sets) untouched.

Built `scripts/X.3/run_x3_eval.py`: reuses `eval/run_eval.py`'s `run_fw` (raw faster-whisper,
language pinned — the "fw-`<size>`-forced" style the brief names), `word_errors`/`char_errors`,
`_rate`/`_ci`/`_macro`/`BOOTSTRAP`, pointed at `uk800`/`en500` instead of `en`/`uk`; writes its own
cache `eval/results/hyp/x3-fw-<model>-forced.jsonl` (never touches `run_eval.py`'s own hyp files)
and its own `scripts/X.3/x3_scores.json`, resumable by clip id exactly like `run_eval.py`.

Investigated turbo-uk convertibility (network used only for this, per node authorization):
`curl` the HF API for `Yehor/whisper-large-v3-turbo-quantized-uk` (compressed-tensors 4-bit
transformers checkpoint, not CTranslate2), downloaded it (`snapshot_download`, 537 MB), attempted
`uv run ct2-transformers-converter --model Yehor/whisper-large-v3-turbo-quantized-uk ...
--quantization int8` — full transcript and cause analysis in `scripts/X.3/turbo_uk_conversion.md`.

Timing probe: `run_x3_eval.py --model large-v2 --limit 3` → 6 decodes (3 uk + 3 en) in 35 s
including model load; `rtf` 1.446 (uk800 sample) / 0.777 (en500 sample). Extrapolating from clip
durations, the full 800+500 forced-language run is on the order of ~2 h CPU wall time per model —
matches the brief's "hours per model" expectation. Launched the full `large-v2` run detached
(`nohup ... > scripts/X.3/large-v2.log 2>&1 &`, pid 482183, independent of this tool session) —
confirmed steady progress before handoff: 28/1300 clips cached after ~2 min (`20/800` uk logged at
94 s), consistent with the ~90-100 min/model estimate. **This background run is the resumable,
long-running part of this node**; see "Resume" below for status/continuation commands.

`large-v2` finished (waited on it via a background `kill -0`-loop, notified on completion): 1300/1300
decodes, 6742 s (~1.87 h) wall. **uk800 forced-language WER 13.10 % (CI95 [11.90, 14.31], n=800,
rtf 1.059); en500 forced-language WER 3.12 % (CI95 [2.63, 3.67], n=500, rtf 0.952).** (uk figure is
close to `CLAUDE.md`'s cited leaderboard large-v2 number, 13.72 % — different harness/normalization,
same ballpark; a real cross-check, not identical setups.) Full record:
`eval/results/hyp/x3-fw-large-v2-forced.jsonl`, `scripts/X.3/large-v2.log`.

Confirmed no other large-`*` model loaded machine-wide (`pgrep -af python`, `free -h`) then launched
`large-v3` the same way (detached, pid 515002 at launch, `scripts/X.3/large-v3.log`), confirmed
progressing.

`large-v3` finished (background wait-loop, notified on completion): 1300/1300 decodes, 7180 s
(~2.0 h). **uk800 forced-language WER 10.97 % (CI95 [9.88, 12.05], n=800, rtf 1.077); en500
forced-language WER 5.19 % (CI95 [3.27, 7.56], n=500, rtf 0.984).** Record:
`eval/results/hyp/x3-fw-large-v3-forced.jsonl`, `scripts/X.3/large-v3.log`.

Ran the paired-bootstrap comparison (`run_x3_eval.py --compare large-v2,large-v3`, no model
loading, seconds):
```
uk: n=800  diff(v2-v3)=+2.13  CI95 [1.24, 3.04]   (excludes 0: v3 significantly better on uk)
en: n=500  diff(v2-v3)=-2.07  CI95 [-4.42, -0.29] (excludes 0: v2 significantly better on en)
```
**Applying the pre-registered rule** ("default = lowest UK WER whose CI vs the runner-up excludes
0, provided its EN WER is within 2.0 pts of the best; if not separable, the cheaper one per X.4"):
lowest UK WER so far is large-v3 (10.97 %), and its CI vs the runner-up (large-v2) excludes 0 — the
first condition holds. But large-v3's EN WER (5.19 %) is **2.07 pts** above the best EN WER seen so
far (large-v2, 3.12 %) — **0.07 pts over the rule's 2.0-pt gate**, and the en-diff CI itself
excludes 0 (this is not noise: [-4.42, -0.29] does not cross zero even at its narrow end). So
large-v3 **fails** the rule's second condition by a small but real margin, and the rule falls back
to "the cheaper one per X.4": X.4 (`review/checkpoint-1/tasks/X.4-per-update-cost.md`) measured
large-v2 faster than large-v3 at every buffer size (e.g. buffer=4s median 4.536 s vs 4.818 s) — so
**per the pre-registered rule as written, the fallback point is large-v2**, not the model with the
better (and significantly better) UK WER. This is a knife-edge result worth flagging verbatim
rather than rounding away; large-v3-turbo's numbers (below) may still change which model is "best"
UK WER and which is "cheapest," but the large-v2-vs-large-v3 pair alone already shows the rule
picking the higher-UK-WER model over a statistically significant 2.13-pt-better alternative because
of a 0.07-pt overshoot on the EN-gap gate.

Confirmed no other large-`*` model loaded machine-wide, then launched `large-v3-turbo` the same
way (detached, pid 549430 at launch, `scripts/X.3/large-v3-turbo.log`), confirmed progressing.

`large-v3-turbo` finished (background wait-loop, notified on completion): 1300/1300 decodes, 4748 s
(~1.32 h — clearly faster wall time than large-v2/large-v3, consistent with its lower `rtf`).
**uk800 forced-language WER 12.36 % (CI95 [11.20, 13.53], n=800, rtf 0.781); en500 forced-language
WER 2.79 % (CI95 [2.35, 3.25], n=500, rtf 0.687).** Record:
`eval/results/hyp/x3-fw-large-v3-turbo-forced.jsonl`, `scripts/X.3/large-v3-turbo.log`.

Ran the two remaining paired-bootstrap comparisons:
```
large-v3 vs large-v3-turbo:
  uk: n=800  diff(v3-turbo)=-1.40  CI95 [-2.36, -0.46]  (excludes 0: v3 significantly better on uk)
  en: n=500  diff(v3-turbo)=+2.40  CI95 [ 0.58,  4.71]  (excludes 0: turbo significantly better on en)
large-v2 vs large-v3-turbo:
  uk: n=800  diff(v2-turbo)=+0.73  CI95 [-0.28,  1.78]  (includes 0: not significant)
  en: n=500  diff(v2-turbo)=+0.33  CI95 [ 0.06,  0.63]  (excludes 0: turbo significantly better on en, small)
```

**Full three-candidate summary (n=800 uk / 500 en, all pairs on the same clips):**

| model | uk WER (CI95) | en WER (CI95) | rtf uk / en | wall (full run) |
|---|---|---|---|---|
| large-v2 | 13.10 [11.90, 14.31] | 3.12 [2.63, 3.67] | 1.059 / 0.952 | 6742 s |
| large-v3 | **10.97** [9.88, 12.05] | 5.19 [3.27, 7.56] | 1.077 / 0.984 | 7180 s |
| large-v3-turbo | 12.36 [11.20, 13.53] | **2.79** [2.35, 3.25] | **0.781 / 0.687** | **4748 s** |

**Re-applying the pre-registered rule with all three measured candidates** ("default = lowest UK
WER whose CI vs the runner-up excludes 0, provided its EN WER is within 2.0 pts of the best; if not
separable, the cheaper one per X.4"): lowest UK WER is large-v3 (10.97 %); its CI vs the actual
runner-up (large-v3-turbo, 12.36 %, not large-v2) excludes 0 ([-2.36, -0.46]) — condition 1 holds.
Condition 2: the best EN WER across all three is now large-v3-turbo's 2.79 %, not large-v2's
3.12 % — large-v3's EN WER (5.19 %) is **2.40 pts** above that best, **0.40 pts past the rule's
2.0-pt gate** (worse margin than the two-candidate-only reading above, corrected here), and the
en-diff CI vs the actual best (turbo) also excludes 0 ([0.58, 4.71]) — again not noise. large-v3
**fails condition 2 clearly** once turbo is in the comparison set.

Fallback ("the cheaper one per X.4") **cannot be executed as literally written**: X.4 only measured
large-v2 and large-v3, not large-v3-turbo, so "per X.4" has no data point for the third candidate.
This eval's own `rtf` figures show large-v3-turbo is unambiguously the fastest of the three
(0.781/0.687 vs ~1.0-1.08 for the other two, and its 4748 s vs 6742-7180 s wall time), but that is
this node's own batch-decode RTF, not X.4's per-update streaming-decode benchmark that the rule
names — using it to break the tie is a reasonable substitution, not what the rule specifies.

**Net effect:** the rule, taken literally, disqualifies large-v3 (the significantly-best UK
performer) on the EN gate, then has no named tie-breaker for the two remaining candidates
(large-v2, large-v3-turbo) because X.4 never measured turbo. Those two are *not* significantly
different on UK WER (13.10 vs 12.36, CI [-0.28, 1.78] includes 0) but turbo is significantly better
on EN (3.12 vs 2.79, CI [0.06, 0.63] excludes 0, small effect) and markedly faster in this harness.
A reasonable, evidence-consistent default among the two the rule can actually compare is
**large-v3-turbo** (matches or beats large-v2 on both languages and is faster), but that is this
node's judgment call filling a gap the rule doesn't cover, not the rule's own mechanical output —
flagged for H1.

## Findings

- [blocking] `Yehor/whisper-large-v3-turbo-quantized-uk` cannot be loaded via the mandated
  `faster_whisper` path in this repo's environment: `ct2-transformers-converter` needs `torch`
  (not a GMST dependency; `ModuleNotFoundError: No module named 'torch'` confirmed directly) and
  fails with an unrelated `NameError: name 'torch' is not defined` at
  `.venv/lib/python3.12/site-packages/ctranslate2/converters/transformers.py:107` rather than a
  clear "install torch" message; separately the checkpoint's `compressed-tensors` 4-bit
  quantization has no converter support path (only `quant_method == "awq"` is special-cased) and
  needs the `compressed_tensors` package to even dequantize on load in `transformers`
  (also absent). Installing either package is outside this node's network authorization (scoped to
  downloading the two turbo repos, not installing into the shared `.venv` other concurrent agents
  use). **Consequence for EVID-03's rule:** the pre-registered rule needs a UK WER number for every
  candidate; turbo-uk — the leaderboard's best UK performer per `CLAUDE.md` (12.75 %) and the
  reason the amendment approved downloading it — cannot produce one at all via this path, not just
  an under-powered pairing as the amendment anticipated for turbo-uk vs large-v2. Full transcript:
  `scripts/X.3/turbo_uk_conversion.md`.
- Corpus WER, forced language, n=800 uk / 500 en (full table and all pairwise CIs above): large-v2
  **13.10 % uk / 3.12 % en**; large-v3 **10.97 % uk / 5.19 % en**; large-v3-turbo **12.36 % uk /
  2.79 % en**. large-v2 vs large-v3 both contradict `CLAUDE.md`'s cited leaderboard ranking
  (leaderboard: large-v2 13.72 % < large-v3 20.53 % on uk, i.e. v2 beats v3) — in this harness
  (forced-language raw faster-whisper, cleaned-CV10 uk800, LibriSpeech en500) **large-v3 beats
  large-v2 on uk by a statistically significant margin** (paired diff +2.13 pts, CI95 [1.24, 3.04]).
  `CLAUDE.md`'s "Model default is provisional" section should not be read as settled evidence of
  v2 > v3 on uk for this task; it cites a different harness/leaderboard, and this node's own
  numbers disagree with it on which of the two is better.
- [blocking] **Applying the pre-registered EVID-03 rule literally to all three measured candidates
  disqualifies the significantly-best-on-uk model and then has no tie-breaker for what's left.**
  Lowest UK WER = large-v3 (10.97 %), CI vs the actual runner-up (large-v3-turbo, 12.36 %) excludes
  0 ([-2.36, -0.46]) — condition 1 ("lowest UK WER whose CI vs the runner-up excludes 0") holds.
  But large-v3's EN WER (5.19 %) is **2.40 pts** above the best EN WER across all three
  (large-v3-turbo, 2.79 %) — **0.40 pts past the rule's 2.0-pt gate**, and that gap is itself
  statistically real (CI [0.58, 4.71] excludes 0) — so large-v3 **fails condition 2**. The rule's
  fallback, "the cheaper one per X.4," **cannot be executed as written**: X.4
  (`tasks/X.4-per-update-cost.md`) only benchmarked large-v2 and large-v3, never large-v3-turbo, so
  there is no X.4 cost figure for the one candidate this eval's own `rtf` shows is clearly the
  cheapest (0.781/0.687 vs ~1.0-1.08 for the other two; 4748 s vs 6742-7180 s wall time for the
  full run). Among the two candidates the rule *can* compare on cost (large-v2, large-v3 — X.4 says
  large-v2 is cheaper), large-v2 and large-v3-turbo are not significantly different on uk (diff
  +0.73 pts, CI [-0.28, 1.78] includes 0) while large-v3-turbo is significantly better on en (diff
  +0.33 pts, CI [0.06, 0.63] excludes 0, small) and faster in this harness — picking large-v3-turbo
  over large-v2 is defensible but is this node's judgment filling a gap in the rule, not the rule's
  own mechanical output. **This is a property of the pre-registered rule (V1, EVID-03) exposed only
  once a third real candidate's numbers exist** — a 2-candidate rule with a hard, CI-blind 2.0-pt
  EN gate and a cost fallback that assumed only 2 candidates would ever need it. Flagged per
  PLAN.md rule 3 ("report ... with magnitudes") for H1's decision, not re-litigated here.

## Resume

All three runnable candidates finished within this session (large-v2, large-v3, large-v3-turbo —
1300/1300 decodes each; results, all three pairwise paired-bootstrap CIs, and the rule application
above). Nothing left running. To reproduce or re-score without re-decoding:

    cd /home/maxymus/code_for_soul/GMST
    uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --score-only
    uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --compare large-v2,large-v3
    uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --compare large-v3,large-v3-turbo
    uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --compare large-v2,large-v3-turbo

turbo-uk has no runnable command — it is blocked (see Findings), not paused. If dependencies change
(e.g. `torch` + `compressed_tensors` become available and someone re-attempts the conversion,
outside this node's authorization), `scripts/X.3/turbo_uk_conversion.md` has the exact failure
point to check against.

## Could not check

- turbo-uk WER: blocked, see Findings — a dependency/environment gap (`torch`, `compressed_tensors`
  not installed, outside this node's network authorization), not a Mac-only issue.

FINDING: findings
