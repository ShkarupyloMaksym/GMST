id: R4
title: Test-suite adequacy
parent: -
stage: review
kind: task
agent: code-reviewer
model: sonnet
effort: medium
status: done
depends-on: -

# R4 — Test-suite adequacy

## Instructions

Audit `tests/` (136 fast tests + 4 slow) against what `PLAN.md` "Testing" and "`reconcile.py` edge cases (each has a test)" promise. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

For each promised test, name the test that covers it or record that none does. Own the onboarding lead: `tests/fixtures/en.wav` / `uk.wav`. Then check that the tests would actually fail if the code were wrong: for the five riskiest guards (your pick, justified — start with `_align`'s −1 on contradiction, the overlap anchor, `trim_to`/`rebase`, the unconditional `sink.close()`, and the drop-oldest queue), apply a one-line mutation in a **scratch copy** of the tree (never the working tree), run the suite there, and record whether it goes red. Save the mutations and outputs in `scripts/R4/`. Run `uv run pytest -m slow` once (offline) and record the result.

## What was read / measured

- Read root `CLAUDE.md`, `PLAN.md` (Testing section L286-298, reconcile edge-case table L221-230),
  `review/checkpoint-1/PLAN.md` rules 1-8, this node file.
- Read `tests/fixtures/README.md` (promises `en.wav`/`uk.wav`), confirmed via `ls tests/fixtures/`
  that only `README.md` is present — no `.wav` files committed.
- Read `src/gmst/reconcile.py` (full, 136 lines) and `tests/test_reconcile.py` (full, 106 lines):
  every edge case in the PLAN.md table (longest-common-prefix, tail-never-agrees/flush, contradiction
  -1, rebase, reset) has a direct unit test on `LocalAgreement`.
- Read `src/gmst/pipeline/stream.py` (full) and `tests/test_stream_pipeline.py` (full, 362 lines):
  `_marked`/`_marked_engine` probes for overlap-seam duplication, trim-bounded-buffer, forced commit
  (time-based and stalled-pushes-based), prompt cap, contradicting shutdown tail, sink.close() on
  engine death.
- Read `src/gmst/segment/endpointer.py` `trim_to()` (L80-92) and `tests/test_endpointer.py` (full):
  `test_trim_to_advances_t0_and_shrinks_buffer` and `test_trim_to_is_a_no_op_inside_the_back_off`
  test only the raw seconds/samples arithmetic of the 0.2s back-off against a `ScriptedVad`
  synthetic boundary — neither test ties the cut point to a real committed *word*'s audio.
- Read `src/gmst/audio/device_source.py` (full) and `tests/test_device_source.py` (full):
  `test_bounded_queue_drops_oldest` directly exercises drop-oldest + `stats.blocks_dropped` +
  `lagging` flag.
- Read `tests/test_config.py`, `test_turns.py`, `test_vad.py`, `test_metrics.py`, `test_sinks.py`,
  `test_sink_base.py`, `test_sse_sink.py`, `test_backend_lid_windows.py`,
  `test_stream_realvad_slow.py` in full — each PLAN.md "Testing" bullet (config validation,
  endpointer synthetic sequences, FakeEngine protocol, fixtures, slow-marker deselection) is
  covered by at least one named test, **except** the `en.wav`/`uk.wav` fixture promise.
- Baseline: `uv run pytest -q` at repo root → `136 passed, 4 deselected in 4.00s`.
- Built scratch copy at `$SCRATCH/gmst_mut` (`cp src tests pyproject.toml`, excluding `.venv`,
  `eval/results`), verified it reproduces the baseline via
  `PYTHONPATH="$PWD/src:$PWD" <repo>/.venv/bin/python -m pytest -q` (using the repo's already-synced
  `.venv` directly rather than `uv run`, to avoid re-resolving/downloading in the scratch copy) →
  `136 passed, 4 deselected in 4.07s`.
- Ran mutation 1 (`reconcile.py` `_align` contradiction `return -1` → `return 0`,
  `scripts/R4/mutation1_align_contradiction.diff`) → **red**: 2 failed
  (`scripts/R4/mutation1_output.txt`).
- Ran mutation 2 (`stream.py` overlap-anchor: `rebase([w.text for w in hyp[:done] if w.end > cut], ...)`
  → `rebase([], ...)`, `scripts/R4/mutation2_overlap_anchor.diff`) → **red**: 1 failed
  (`scripts/R4/mutation2_output.txt`, duplicate words `w15,w15,w20,w20,...`).
- Ran mutation 3 (`stream.py` trim-path anchor filter removed but non-empty:
  `hyp[:done] if w.end > cut` → `hyp[:done]` unfiltered,
  `scripts/R4/mutation3_trim_rebase.diff`) → **green**: 13 passed, no test caught it
  (`scripts/R4/mutation3_output.txt`). Investigated why: `LocalAgreement._align` matches only the
  *suffix* of the anchor against the new hypothesis prefix (`self._committed[-k:]`), so a
  too-long-but-correctly-ordered anchor is harmless — only an anchor that is wrong/missing at the
  tail matters. Followed up with mutation 3b (empty anchor on the trim path, same shape as mutation
  2) → **red**: 3 failed (`scripts/R4/mutation3b_output.txt`,
  `scripts/R4/mutation3b_trim_rebase_empty_anchor.diff`), confirming the guard *is* tested for the
  failure mode that actually matters (empty/missing anchor), just not for an over-long one (which
  is not a bug).
- Mutation 4 (unconditional `sink.close()` in `run_stream`'s outer `finally` made conditional by
  removing the inner `try/except Exception` around the final-flush decode,
  `scripts/R4/mutation4_sink_close.diff`): applied but the sandboxed Bash tool returned repeated
  transient "auto mode classifier gave no verdict" errors on every retry for the run command; timed
  out before a result was obtained. Diff and command are saved for a rerun.
- Ran mutation 4 (unconditional `sink.close()`) after Bash tool recovered from transient
  "auto mode classifier" errors: **red**: 1 failed
  (`scripts/R4/mutation4_output.txt`: `assert p.exists()` fails once the inner `try/except` around
  the final-flush decode is removed and the flush decode raises again).
- Ran mutation 5 (`device_source.py` `feed()`: drop-oldest → drop-newest, i.e. on `queue.Full` just
  count the drop and discard the incoming block instead of evicting the head,
  `scripts/R4/mutation5_drop_oldest_queue.diff`) → **green**: `tests/test_device_source.py`
  9 passed, nothing caught it (`scripts/R4/mutation5_output.txt`). Root cause: `_src()` in the test
  file feeds five *identical* `np.zeros(...)` blocks, so `blocks_in`, `blocks_dropped`, `q.qsize()`
  and `lagging` are all identical whichever end of the queue is evicted — the test cannot tell "kept
  the 3 newest" from "kept the 3 oldest, forever". Confirmed with a value-marked probe
  (`scripts/R4/queue_content_probe.py`, run against the real unmodified code): feeding blocks marked
  `0.0, 0.1, 0.2, 0.3, 0.4` through a maxsize-3 queue leaves the **three most recent** marks in the
  queue; the script prints that a drop-newest bug would leave the exact same `blocks_in`/
  `blocks_dropped`/`qsize` while silently keeping the *three oldest* forever.
- Ran `HF_HUB_OFFLINE=1 uv run pytest -m slow -q` from the repo root (checked `pgrep -af python`
  first: only the shell harness itself was running) → `3 passed, 1 skipped, 136 deselected in 1.23s`
  (`scripts/R4/slow_suite_output.txt`). The skip is `test_mlx_lid_model_is_the_cached_transcribe_model`
  (`importorskip("mlx.core")`, correctly unavailable on Linux).
- Also read `tests/test_cli.py`, `tests/test_bench.py`, `tests/test_batch_pipeline.py`,
  `tests/test_fakes.py`, `tests/fakes.py`, `tests/test_metrics.py`, `tests/test_sinks.py`,
  `tests/test_sink_base.py`, `tests/test_sse_sink.py`, `tests/test_turns.py`, `tests/test_vad.py`,
  `tests/test_config.py`, `tests/test_backend_lid_windows.py`,
  `tests/test_stream_realvad_slow.py` in full to check every "Testing" bullet has a named test.
- Stopped here: all five mutations run and recorded, slow suite run once, fixture gap confirmed.
  Did not additionally mutate `endpointer.trim_to`'s back-off constant itself (R1 already owns and
  reported that specific defect; see finding below for why R4's own probes corroborate it) or dig
  further into `test_bench.py`/`test_cli.py` internals beyond confirming test names exist, since the
  brief's explicit five-guard list was satisfied.

## Findings

- **[blocking]** `tests/test_device_source.py::test_bounded_queue_drops_oldest` cannot tell
  drop-oldest from drop-newest, so a reversal of the documented failure-mode policy
  (`CLAUDE.md`: "bounded `audio_queue` (drop-oldest + `[lagging]` flag when the engine falls
  behind)") would ship silently. `src/gmst/audio/device_source.py:150-158` is the only place that
  policy is implemented. Mutation 5
  (`review/checkpoint-1/scripts/R4/mutation5_drop_oldest_queue.diff`) replaces the evict-head-then-
  enqueue with "count the drop, discard the incoming block" (i.e. drop-**newest**) — a one-line
  change that keeps the *stalest* audio in the queue forever once it fills, the opposite of what a
  live-captioning session needs. Result: `9 passed` in `tests/test_device_source.py`
  (`scripts/R4/mutation5_output.txt`) — the test suite does not notice. Root cause: the test feeds
  five identical `np.zeros(...)` blocks, so `blocks_in`, `blocks_dropped`, `q.qsize()` and `lagging`
  are the same regardless of which end of the queue is evicted. `scripts/R4/queue_content_probe.py`,
  run against the *real*, unmutated code, confirms the surviving queue entries are content-dependent:
  feeding marks `0.0, 0.1, 0.2, 0.3, 0.4` through the maxsize-3 queue leaves the three most recent
  marks (`0.13, 0.2, 0.26` after resampling) — proof the current code is in fact correct, and equally
  proof that the existing test is not exercising the property it is named for. A one-line assertion
  on block *content* (not just counts) after overflow would have caught this.

- **[serious]** `PLAN.md:295` and `tests/fixtures/README.md` promise `tests/fixtures/en.wav` and
  `uk.wav`, committed, for LID tests ("Keep them short and commit them... commit"). Verified:
  `ls tests/fixtures/` → only `README.md`; no `.wav` file exists anywhere in `tests/fixtures/`.
  No test in the suite reads `tests/fixtures/en.wav` or `uk.wav` (`grep -r fixtures/en.wav\|uk.wav
  tests/` — no hits); `tests/test_lid.py` tests `resolve_language` purely on synthetic
  `(lang, prob, candidates)` tuples, and `tests/test_backend_lid_windows.py` stubs the model with
  `_RecordingModel` rather than loading real audio. The onboarding lead this node was asked to own
  is confirmed exactly as suspected: the promised end-to-end "does the model actually call `uk` on
  clear Ukrainian speech / `en` on clear English speech" check does not exist anywhere in the suite —
  every LID test operates on numbers the test author chose, not on real EN/UK audio.

- **[serious]** `src/gmst/segment/endpointer.py:80-92` (`trim_to`) and its only tests
  (`tests/test_endpointer.py::test_trim_to_advances_t0_and_shrinks_buffer`,
  `test_trim_to_is_a_no_op_inside_the_back_off`) verify only the raw seconds/samples arithmetic of
  the `_TRIM_BACKOFF_S` = 0.2 s back-off against an arbitrary `ScriptedVad` boundary — they never tie
  the cut point to a real committed word's audio span. This is exactly why the suite stayed green
  through R1's reported defect (`trim_to` cuts 0.2 s before the **end** of the last committed word,
  landing *inside* that word rather than before it): no unit test asserts the back-off lands outside
  the word's own audio. Separately, the seam-level probes that could in principle catch the
  consequence (`test_stream_pipeline.py::test_committed_audio_is_trimmed_so_the_decoded_buffer_stays_bounded`,
  `test_forced_cut_never_re_commits_the_overlap_or_moves_time_backwards`) are built on `_marked()`
  audio whose amplitude only changes at 0.5 s chunk boundaries (`chunk_seconds=0.5` default) — coarser
  than the 0.2 s back-off — so `_marked_engine` reads back the *same* word mark whether the cut lands
  at the true word boundary or 0.2 s inside it, and the bug produces no observable duplicate or
  mismatch in these tests. Demonstrated directly: mutation 3
  (`scripts/R4/mutation3_trim_rebase.diff`, widening the trim-path anchor beyond what actually
  survived the cut — a related but distinct "anchor too generous" defect) also passed all 13 tests
  in `test_stream_pipeline.py` untouched (`scripts/R4/mutation3_output.txt`), confirming these seam
  tests only catch an anchor that is *missing*, not one that is *imprecise* — which is the shape of
  R1's finding. (Mutation 3b, an emptied anchor, was caught — `scripts/R4/mutation3b_output.txt` —
  showing the harness is not blind to every trim/rebase defect, just to sub-chunk-granularity ones.)

- **[minor]** Every other "Testing" promise in `PLAN.md:286-298` has a directly-named covering test:
  `FakeEngine`/`tests/fakes.py` → `test_fakes.py` (protocol conformance, script advance-then-repeat,
  scripted LID); `reconcile.py` edge-case table (L221-230) → each row has a dedicated test in
  `test_reconcile.py` (`test_commits_only_the_agreed_prefix`, `test_flush_force_commits_pending_tail`,
  `test_stalled_pushes_counter`, `test_revised_prefix_never_re_commits`,
  `test_flush_drops_a_tail_it_cannot_place`, `test_rebase_re_anchors_on_the_audio_that_survived_a_trim`,
  `test_normalized_comparison_ignores_case_and_trailing_punctuation`) plus the seam-level
  `test_stream_pipeline.py` tests for the overlap/trim/forced-commit/prompt-cap rows; `endpointer.py`
  synthetic sequences → `test_endpointer.py`; `config.py` validation/precedence/`auto`
  sentinel/`--config` → `test_config.py` (14 tests) + `test_cli.py::test_config_is_loaded_and_validated`;
  slow-marker deselection → verified directly (`136 passed, 4 deselected` fast,
  `3 passed, 1 skipped, 136 deselected` under `-m slow`). Mutations 1, 2 and 4 (the three riskiest
  guards not already flagged above) all went **red** as designed:
  contradiction-disabled (`scripts/R4/mutation1_output.txt`, 2 failed), overlap-anchor-dropped
  (`scripts/R4/mutation2_output.txt`, 1 failed, duplicate words `w15,w15,w20,w20,...`), and
  sink.close()-made-conditional (`scripts/R4/mutation4_output.txt`, 1 failed,
  `assert p.exists()` false) — these three guards are adequately tested.

## Could not check

- `mlx_whisper` backend tests (`test_backend_lid_windows.py::test_mlx_lid_model_is_the_cached_transcribe_model`)
  need Apple hardware; correctly skipped here (`importorskip`) rather than failing.
- Real-audio LID accuracy (whether the model actually says `en`/`uk` on real speech, which the
  missing `en.wav`/`uk.wav` fixtures were meant to exercise) could not be measured at all — there is
  no fixture to run it against; flagged as a finding above rather than measured.
- Did not attempt real-hardware timing or BlackHole/device tests (out of scope for this node; R3
  owns capture/device failure modes).

FINDING: findings
