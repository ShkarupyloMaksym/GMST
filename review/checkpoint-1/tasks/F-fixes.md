id: F
title: Fixes (group; T1 creates F.1 …)
parent: -
stage: fix
kind: group
agent: orchestrator
model: sonnet
status: done
depends-on: T1, H1

# F — Fixes (group; T1 creates F.1 …)

## Instructions

Placeholder group. T1 creates one child per group of related FIX items (and H1 adds those its decisions imply). Each fix lands with a test that fails before it and passes after, and the full suite green.

## What was read / measured

Synthesis (2026-09-29): 20 fix nodes, all done. F.1–F.7 from T1's FIX items; F.8–F.11 and F.13
from DECIDE-01…05; F.12 → F.18 → F.20 the glossary's three designs (the first two failed X.6 /
X.6b); F.14 → F.15 → F.16 → F.17 the streaming seam, each driven by an evidence run on clips the
previous fix had not seen, ending in two-pass (DECIDE-09); F.19 the default model (DECIDE-10).
Suite 136 → 200 (+5 slow), ruff clean. Per-fix detail and commits: each F.n node;
`review/checkpoint-1/changes.md`.

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: recorded
