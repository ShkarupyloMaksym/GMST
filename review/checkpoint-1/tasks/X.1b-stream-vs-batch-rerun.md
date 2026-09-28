id: X.1b
title: EVID-01 re-measured after F.14 (same pre-registered rule)
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: F.14

# X.1b — EVID-01 re-measured after F.14 (same pre-registered rule)

## Instructions

Re-run `scripts/X.1/run_wer.py` unchanged (copy it to `scripts/X.1b/` first, adding only output
paths) on the same clips with `small` then `large-v2`, en and uk (language pinned); mixed with
`small` only (auto LID, now after F.11 and F.14). Report against V1's EVID-01 rule, unchanged:
holds if stream ≤ batch + 3.0 pts on en and uk with small and contradicted pushes ≤ 10 %. Also save
the full stream output text per set. Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md`,
`tasks/V1-evidence-plan.md`, `tasks/X.1-*.md`, `tasks/X.1.1-*.md`, this file. Offline; you are the
only process loading models; work from the main tree's `.venv` (no clone); write only this node
file and `scripts/X.1b/`.

## What was read / measured

Read: root `CLAUDE.md`; `review/checkpoint-1/PLAN.md` rules 1-8; `tasks/V1-evidence-plan.md`
(pre-registered EVID-01 rule, unchanged: **holds** if corpus stream WER ≤ batch WER + 3.0 pts on en
and uk with `small`, and contradicted-push share ≤ 10%); `tasks/X.1-stream-vs-batch-wer.md` (prior
run, pre-F.14: en +4.32pts, uk +3.50pts, both fail; contradicted 0% on all sets); `tasks/X.1.1-*.md`
(attributed the gap to the prompt overlapping buffer audio — 20/21 en deletions were skipped-anchor
words — fixed in F.14: `gmst/pipeline/stream.py` prompt is now `committed[:-len(agree.committed)]`,
confirmed present at `src/gmst/pipeline/stream.py:201-213`, "only text whose audio is no longer in
the buffer"); `tasks/F.14-prompt-excludes-buffer.md`.

Copied `scripts/X.1/run_wer.py` to `scripts/X.1b/run_wer.py` unchanged except output-path strings
(`sed 's#scripts/X.1/#scripts/X.1b/#g'`); diffed `clips.txt` from X.1 (`diff` → identical, same first
20 en/uk clips and first 20 mixed `inter` clips by manifest order). `pgrep -af python` before each
run: only KDE plasmoid helpers and an unrelated `zsh` loop waiting on a curl download (per
coordinator's note) — no other Python. Ran from the main tree's `.venv`, offline
(`HF_HUB_OFFLINE=1`), no clone made.

`small` run: `uv run python review/checkpoint-1/scripts/X.1b/run_wer.py small en uk mixed`
(`small_run.log`, `small_results.json`), shipped-default engine (`faster_whisper`,
`per_segment_lid=True`, `compute_device=cpu`, `compute_type=int8`), started 15:20, finished ~15:44
(~24 min wall), no other Python process running throughout (checked before start and again during
polling).

`large-v2` run: budget after the `small` run and setup left too little of the ~60 min for a full
en+uk large-v2 run (X.1's large-v2 en+uk alone took 2364s ≈ 39 min). Per this node's pre-authorized
fallback, started `large-v2` on **en only**
(`uv run python review/checkpoint-1/scripts/X.1b/run_wer.py large-v2 en`, `large-v2_run.log`),
started 15:44. Batch finished (115.1s, matches X.1's pre-F.14 large-v2 batch number exactly — batch
never touches the stream prompt path, as expected). Stream (en, large-v2) was still running when the
`Bash` tool started failing at the harness level ("server-side auto mode classifier gave no verdict")
around 16:04 and did not recover after one retry plus several `Read`-only checks of the log
(unchanged); no further polling or process control was possible. See Could not check.

## Findings

Pre-registered rule (V1, EVID-01, unchanged): **holds** if corpus stream WER ≤ batch WER + 3.0 pts
on en and uk with `small`, and contradicted-push share ≤ 10%.

**`small` run** (`scripts/X.1b/run_wer.py small en uk mixed`, `small_results.json`; shipped defaults,
same 20/20/20 clips as X.1 — `clips.txt` identical):

| set | mode | WER | edits/ref | elapsed | decodes | contradicted/pushes |
|---|---|---|---|---|---|---|
| en | batch | 2.64% | 11/417 | 24.1s | — | — |
| en | stream | **2.64%** | 11/417 | 392.8s | 179 | 0/179 |
| uk | batch | 23.78% | 34/143 | 22.2s | — | — |
| uk | stream | **45.45%** | 65/143 | 161.4s | 98 | 0/98 |
| mixed-inter | batch | 11.02% | 65/590 | 89.1s | — | — |
| mixed-inter | stream | 19.49% | 115/590 | 699.8s | 294 dec / 209 pushes | 0/209 |

- en: stream − batch = 2.64 − 2.64 = **0.00 pts**, and the edit count matches exactly (11/417 both
  ways) — passes the margin cleanly. Confirms X.1.1's attribution and F.14's fix: the prompt no
  longer overlaps buffer audio, so the word-dropping at utterance joins X.1 measured (+4.32 pts
  pre-fix) is gone on this set.
- uk: stream − batch = 45.45 − 23.78 = **+21.67 pts**, six times the pre-fix gap X.1 measured
  (+3.50 pts) and roughly seven times the 3.0-pt threshold. **[blocking]** F.14 did not just fail to
  close the uk gap — it made it dramatically worse. `small_results.json`'s uk stream `out_preview`
  contains inserted tokens that are not language output at all: `"Zum2i"`, `"оssoof1"` (mixed
  Latin/Cyrillic garbage, not present anywhere in `ref_preview` or in the batch hyps for the same
  clips) — e.g. stream out `...Тому, може не зробити це прайдень, і ті бутті, Zum2i, і осьoof1,
  вигнути, то, це все. Так, Zum2i величається тут...` against ref `...тут великоросам нема сенсу
  лукавити хто попіксся окропом на воду дує...`. `committed_words` (169) exceeds `ref_words` (143)
  for this set — the stream path is *inserting* words on uk, not only dropping them, which is a
  different failure mode than the one F.14 targeted (X.1.1 only found deletions, on en).
- mixed-inter (not part of the pre-registered rule, reported as instructed): stream − batch =
  19.49 − 11.02 = **+8.47 pts**, better than X.1's pre-F.14 +22.37 pts but still far over the
  3.0-pt bar that applies to en/uk; sample text in `out_preview` is legible (no garbage tokens seen
  in the first 300 chars), unlike uk.
- contradicted-push share: en 0/179, uk 0/98, mixed 0/209 = **0%** on every set — same as X.1,
  F.8's fix still holds; the uk regression is not a contradiction-path failure.

**Net against the rule:** en now passes (0.00 pts); uk fails far more severely than before F.14
(+21.67 pts vs the pre-fix +3.50 pts). The rule requires both en **and** uk to pass — it does not,
so **DECIDE-01 remains reopened**, now on stronger and more specific evidence: F.14's prompt change
(removing the anchor-word overlap from the prompt) trades an en deletion bug for a uk
hallucination/insertion bug of much larger magnitude on this sample. The shipped-default streaming
path is not safe for Ukrainian audio as measured here, independent of whether the underlying model is
`small` or `large-v2` (see below — large-v2 batch is unaffected, and X.1 already showed the pre-fix
stream/batch gap does not close by upsizing the model).

**`large-v2`, en only (partial — see Could not check for uk and for the stream number):** batch
1.68% (7/417, 115.1s) — identical to X.1's pre-F.14 large-v2 en batch number, as expected (batch does
not use the stream prompt). The stream side did not finish inside this node's budget/tooling window,
so no large-v2 stream WER (en) and no large-v2 uk numbers (batch or stream) were obtained in this
node.

## Could not check

- **large-v2 uk (batch and stream), and large-v2 en stream did not complete.** Budget: the `small`
  run alone took ~24 min; X.1's large-v2 en+uk together took ~39 min, so a full en+uk large-v2 rerun
  was not attempted (per this node's pre-authorized fallback, en-only was started). Even en-only did
  not finish: partway through the large-v2 stream decode, the `Bash` tool began returning
  `"The server-side auto mode classifier gave no verdict (error)"` on every call (a harness-level
  failure, not a code or model problem) and did not recover after a retry; `Read`-only checks of
  `large-v2_run.log` showed no further progress (file unchanged) but a `Read` cannot poll with a
  wait, list processes, or terminate the background job. The `large-v2 en` process
  (`review/checkpoint-1/scripts/X.1b/run_wer.py large-v2 en`, started ~15:44) may still be running
  and writing to `scripts/X.1b/large-v2_run.log` / `large-v2_results.json` after this handback —
  **the orchestrator should check `pgrep -af run_wer.py` before starting any other node that loads a
  `large-*` model**, and can read `large-v2_results.json` directly if the run completed after this
  session ended (it writes results incrementally per set/mode, per the script's `main()`).
- Per-clip attribution inside the stream WER is not available for the same reason as X.1: stream
  ref/hyp comparison is one corpus-level edit distance over the whole concatenation, not a per-clip
  breakdown.

FINDING: findings
