# What the checkpoint-1 review changed (2026-09-28 … 29)

Basis `checkpoint-1` (8beade7) → branch `review-checkpoint-1`. 7 review nodes → 40 triaged
findings (7 blocking) → 10 decisions by the user → 20 fix nodes → 13 evidence runs, each
pre-registered before it ran. Suite 136 → 200 tests (+5 slow); ruff clean.

## The headline

| | before | after |
|---|---|---|
| live streaming | lost ~85 % of each utterance on real speech (stream WER 0.878 vs batch 0.015, R1) | two-pass: final text = each utterance decoded whole; on unseen clips it matches batch (turbo: en 2.34 vs 3.22 %, uk 6.25 vs 6.25 %, X.1e) |
| language detection | any label (`tr`, `ar`, `bg`…; 11/12 Ukrainian utterances wrong with tiny, R2) | restricted to `lid_languages` (en, uk; ru folded into uk), ≥ 95 % at 3 s (X.2) |
| batch per-segment LID | relabelled faster-whisper's single autodetect | each VAD region decoded in its own language |
| default model | `large-v3`, "provisional", chosen from a leaderboard that did not reproduce | `large-v3-turbo`: uk 12.36 % / en 2.79 %, fastest (X.3, DECIDE-10) |
| shutdown | SIGTERM lost the tail; 2nd Ctrl-C did not abandon; SRT could be empty | SIGTERM = Ctrl-C; 2nd signal exits 130 keeping live-agreed words (`salvage`) |
| eval harness | cache mixed models; per-clip mean WER; no CIs; misaligned mixed clips | per-model cache; corpus WER + bootstrap CIs; paired `--compare`; honest mixed set |

## Decisions (H1; root PLAN.md "Review decisions")

DECIDE-01 re-anchoring (UFAL-style; reopened by X.1–X.1c, closed by X.1d/X.1e under DECIDE-09) ·
02 `lid_languages` · 03 batch per-region LID · 04 stream LID settles at 3 s · 05 runtime status to
stderr/console/JSONL/SSE · 06 public data for the English-terms case (uk-pods terms set) · 07 CI
claim struck · 08 glossary — fed to Whisper (failed X.6), post-correction (failed X.6b), now
curated-only and experimental · 09 two-pass streaming · 10 default model `large-v3-turbo`.

## Fixes (F.1 … F.20)

F.1 shutdown/signals · F.2 eval harness · F.3 bench (shipped path, measured per-update cost, exit
2, `warmup --bench`) · F.4 backends (mlx extra pinned, eager load, honest hint) · F.5 tests (queue
content, real en/uk fixtures, env isolation) · F.6 `sse_port 0`, punctuation tokens, prompt cap
560 · F.7 documents · F.8 trim/time alignment · F.9 `lid_languages` · F.10 batch regions · F.11
LID settling · F.12 glossary (superseded) · F.13 runtime status · F.14 prompt excl. buffer
(superseded) · F.15 anchor prompt + gated time cut + 5-word history · F.16 utterance-local prompt ·
F.17 two-pass · F.18 glossary post-correction · F.19 default model · F.20 curated glossary.

## What the evidence runs taught (and the traps they left in CLAUDE.md)

- Diagnosis on a clip set and evidence on the same set are not the same: F.15 looked like a pass on
  X.1's clips and failed on unseen ones (X.1c). Every verdict since is on rows nothing else used.
- Whisper regurgitates its prompt: committed text from earlier utterances (X.1c) and glossary
  terms (X.6) both produced loops and hallucinations. The prompt now holds only the current
  utterance's words, and never the glossary.
- On a CPU the large models are ~8× too slow for live updates (X.4); the ≲ 3 s target depends on
  the Mac (MAC-03).

## Open (listed in root PLAN.md "Open after the checkpoint-1 review")

Mac: MAC-01 … MAC-06. Deferred: a decode timeout; LID runs twice per utterance under two-pass;
`Yehor/whisper-large-v3-turbo-quantized-uk` needs `torch` to convert; real IT-meeting audio for
the glossary; `large-v2` two-pass uk +3.48 pts (not the default).
