id: R7
title: Clean-clone reproduction
parent: -
stage: review
kind: task
agent: repro-runner
model: sonnet
effort: low
status: todo
depends-on: -

# R7 — Clean-clone reproduction

## Instructions

From a clean clone of tag `checkpoint-1` in your scratchpad (`git clone --branch checkpoint-1 <repo> <scratch>/gmst` — cloning is the one git use allowed), follow `README.md` "Setup" and "Usage" literally, offline where the model is cached. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

Record every step that fails or needs knowledge the docs don't give. Run: `uv sync`, `uv run pytest -q`, `uv run pytest -m slow -q`, `uv run ruff check .`, `uv run gmst devices`, `uv run gmst batch` on one clip from `eval/results/data/uk/` with `--language uk` and with auto LID, and `uv run gmst bench` on one clip with a reference, all with `GMST_MODEL=tiny`. Compare counts and outputs with what the docs claim. Delete the clone when done.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
