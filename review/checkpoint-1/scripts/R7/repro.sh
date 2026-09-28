#!/usr/bin/env bash
# R7 — clean-clone reproduction of checkpoint-1 (8beade7), following README.md "Setup"/"Usage"
# literally. Run from repo root; clones into a scratch dir, runs the documented commands, then
# deletes the clone. Offline only (HF_HUB_OFFLINE=1); GMST_MODEL=tiny where a knob exists.
#
# This is a record of the exact commands run for the R7 node's findings — re-running it requires
# the same HF cache (tiny/large-v2/large-v3/large-v3-turbo already downloaded; the
# Yehor/whisper-large-v3-turbo-quantized-uk repo is NOT cached, so that bench row is expected to
# fail offline, as it did in the recorded run).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRATCH="${1:-/tmp/gmst-r7-clone}"

rm -rf "$SCRATCH"
git clone --branch checkpoint-1 "$REPO_ROOT" "$SCRATCH"
cd "$SCRATCH"
git log -1 --oneline   # expect 8beade7

uv sync

# 1. Full suite, WITHOUT GMST_MODEL set (baseline — should be 136 passed / 4 deselected)
HF_HUB_OFFLINE=1 uv run pytest -q

# 2. Full suite WITH GMST_MODEL=tiny set, as R7's brief instructs — reproduces a real failure
#    (test_config.py::test_defaults_when_no_file asserts cfg.model_size == "large-v3" without
#    clearing GMST_* env vars first)
HF_HUB_OFFLINE=1 GMST_MODEL=tiny uv run pytest -q || true

# 3. Isolate: same test alone, without the env var — passes
HF_HUB_OFFLINE=1 uv run pytest -q tests/test_config.py::test_defaults_when_no_file

# 4. Slow tests, offline (mlx skip expected — no mlx on Linux)
HF_HUB_OFFLINE=1 uv run pytest -m slow -q -rs

# 5. Lint
uv run ruff check .

# 6. devices
HF_HUB_OFFLINE=1 GMST_MODEL=tiny uv run gmst devices

# 7. batch --language: gmst batch has NO --language flag (only stream does) — use GMST_LANGUAGE
CLIP="$REPO_ROOT/eval/results/data/uk/uk-1206.wav"
HF_HUB_OFFLINE=1 GMST_MODEL=tiny GMST_LANGUAGE=uk   uv run gmst batch "$CLIP" -o /tmp/r7-batch-uk.jsonl
HF_HUB_OFFLINE=1 GMST_MODEL=tiny                    uv run gmst batch "$CLIP" -o /tmp/r7-batch-auto.jsonl
cat /tmp/r7-batch-uk.jsonl
cat /tmp/r7-batch-auto.jsonl

# 8. bench: ignores GMST_MODEL entirely (hardcoded Phase-1 candidate list); one candidate
#    (Yehor/whisper-large-v3-turbo-quantized-uk) is not in the HF cache and fails offline —
#    `gmst warmup` (Setup step) only downloads the single *configured* model, not bench's 4
#    candidates, so Setup does not prepare the cache Usage's bench example needs.
printf '%s\n' "взяв єси на одур мене з тими вивідами еге ж" > /tmp/r7-ref.txt
HF_HUB_OFFLINE=1 GMST_MODEL=tiny uv run gmst bench "$CLIP" --ref /tmp/r7-ref.txt
echo "bench exit code: $?"   # observed: 0, even with a failed candidate row

cd /
rm -rf "$SCRATCH"
