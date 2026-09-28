id: T1
title: Triage: merge, dedupe and number the findings
parent: -
stage: triage
kind: task
agent: orchestrator
model: opus
effort: high
status: todo
depends-on: R1, R2, R3, R4, R5, R6, R7

# T1 — Triage: merge, dedupe and number the findings

## Instructions

Read every review node's findings. Deduplicate, re-grade on the one scale (PLAN.md rule 2), and give each an ID: `FIX-nn` (clear fix, no decision needed), `DECIDE-nn` (needs the user), `EVID-nn` (needs a measurement first), `MAC-nn` (needs Apple hardware). Write the table here. Create one `F.n` child of `F` per group of related FIX items, and hand EVID items to V1.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
