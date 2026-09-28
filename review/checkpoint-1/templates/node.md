id: <PARENT>.<n>
title: <what this node checks, as a phrase>
parent: <PARENT>
stage: review
kind: task
agent: <a .claude/agents name | orchestrator | human>
model: <opus | sonnet | haiku>
effort: <low | medium | high>
status: todo
depends-on: -

# <PARENT>.<n> — <title>

## Instructions

<What to read, what to check, and what counts as a finding. Read first: root `CLAUDE.md`,
`review/checkpoint-1/PLAN.md` (rules 1–6), this file. Set `status: in-progress` before starting.>

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
