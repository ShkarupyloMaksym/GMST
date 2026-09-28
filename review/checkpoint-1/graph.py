#!/usr/bin/env python3
"""Derive the checkpoint-1 review graph from its node files.

    python3 graph.py            # from review/checkpoint-1/, standard library only

Writes three GENERATED files, never hand-edited:
  STATUS.md       the table, what can start now, and what is waiting on what
  graph.json      nodes + edges + derived state (what the dashboard renders)
  dashboard.html  dashboard.template.html with graph.json inlined -- the page published as the
                  "Review Graph" artifact

THE NODE FILE IS THE SINGLE SOURCE OF TRUTH (resumable-investigation skill). Each node is
`tasks/<ID>-<slug>.md` with header lines at the top:

    id:          A2.1                     dotted: a child's id extends its parent's
    title:       ...
    parent:      A2                       or "-" for a top-level node
    stage:       review | triage | plan | evidence | decision | fix | close
    kind:        task | group             a group's status is derived from its children
    agent:       a .claude/agents name, "orchestrator", or "human"
    model:       opus | sonnet | haiku | human | -
    effort:      low | medium | high      optional
    status:      todo | in-progress | done | blocked
    depends-on:  A1, A2                   or "-"

and body sections `## Instructions`, `## What was read / measured`, `## Findings`,
`## Could not check`, then a last line `FINDING: clean | findings | recorded | blocked`.

DEEPENING A PART OF THE REVIEW = adding files. A new node `E1.1.a` with `parent: E1.1` becomes E1.1's
child. If its parent is a task, the parent is promoted to a group automatically (its own file still
holds its instructions and any findings). Nothing else changes.

Derived state, per node:
  INCOMPLETE  `done` without a FINDING line or without a "What was read / measured" section
  ready       `todo` and every dependency done
  waiting     `todo` with an unfinished dependency (the dashboard names which)
Findings: every `[blocking]`, `[serious]`, `[minor]` tag inside `## Findings` is counted, except inside a
`### From ...` subsection (a group restating its children's findings).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"
STAGES = ("review", "triage", "plan", "evidence", "decision", "fix", "close")
STAGE_LABEL = {"review": "Review", "triage": "Triage", "plan": "Evidence plan",
               "evidence": "Evidence", "decision": "Decisions", "fix": "Fixes", "close": "Close-out"}
STATUSES = ("todo", "in-progress", "done", "blocked")
MODELS = ("opus", "sonnet", "haiku", "human", "-")
KINDS = ("task", "group")
FINDING_VALUES = ("clean", "findings", "recorded", "blocked")
SEVERITIES = ("blocking", "serious", "minor")
REQUIRED = ("id", "title", "parent", "stage", "kind", "agent", "model", "status", "depends-on")


def header(text: str, name: str) -> str:
    m = re.search(rf"^{re.escape(name)}:\s*(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def section(text: str, title_regex: str) -> str | None:
    m = re.search(rf"^##\s+{title_regex}[^\n]*\n(.*?)(?=^##\s|^FINDING:|\Z)", text,
                  re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None


def listing(value: str) -> list[str]:
    return [] if value in ("", "-") else [v.strip() for v in value.split(",") if v.strip()]


def placeholder(body: str | None) -> bool:
    return body is None or not body.strip() or body.strip().startswith("_(")


def load() -> tuple[dict[str, dict], list[str]]:
    nodes: dict[str, dict] = {}
    errors: list[str] = []
    for path in sorted(TASKS.glob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        h = {k: header(text, k) for k in REQUIRED + ("effort",)}
        missing = [k for k in REQUIRED if not h[k]]
        if missing:
            errors.append(f"{path.name}: missing header(s) {', '.join(missing)}")
            continue
        nid = h["id"]
        if not path.name.startswith(nid + "-"):
            errors.append(f"{path.name}: file name must start with its id '{nid}-'")
        for key, allowed in (("stage", STAGES), ("status", STATUSES), ("model", MODELS),
                             ("kind", KINDS)):
            if h[key] not in allowed:
                errors.append(f"{path.name}: {key} '{h[key]}' not in {allowed}")
        if nid in nodes:
            errors.append(f"{path.name}: duplicate id {nid}")
            continue
        finding_lines = [v for v in re.findall(r"^FINDING:\s*(\S+)", text, re.MULTILINE)
                         if not v.startswith("_(")]           # the template placeholder is not a finding
        findings_body = section(text, r"Findings")
        sev = {s: 0 for s in SEVERITIES}
        if findings_body:
            # a group's "### From <children>" subsections restate child findings: not counted again
            findings_body = re.sub(r"^###\s+From\b.*?(?=^###\s|\Z)", "", findings_body,
                                   flags=re.MULTILINE | re.DOTALL)
            for s in SEVERITIES:
                sev[s] = len(re.findall(rf"\[{s}\]", findings_body, re.IGNORECASE))
        instructions = section(text, r"Instructions") or ""
        nodes[nid] = dict(
            id=nid, title=h["title"], parent=None if h["parent"] in ("", "-") else h["parent"],
            stage=h["stage"], kind=h["kind"], agent=h["agent"], model=h["model"],
            effort=h["effort"] or None, status=h["status"], depends_on=listing(h["depends-on"]),
            finding=finding_lines[-1] if finding_lines else None,
            has_read_section=not placeholder(section(text, r"What was (read|measured|done)")),
            severity=sev, file=f"tasks/{path.name}",
            summary=instructions.split("\n\n")[0].replace("\n", " ")[:400],
            instructions=instructions[:4000],
            findings_text=(findings_body or "")[:4000],
        )
    for n in nodes.values():
        if n["parent"] and n["parent"] not in nodes:
            errors.append(f"{n['id']}: parent '{n['parent']}' does not exist")
        if n["parent"] and not n["id"].startswith(n["parent"] + "."):
            errors.append(f"{n['id']}: a child's id must extend its parent's ('{n['parent']}.')")
        for d in n["depends_on"]:
            if d not in nodes:
                errors.append(f"{n['id']}: depends on unknown '{d}'")
        if n["finding"] and n["finding"] not in FINDING_VALUES:
            errors.append(f"{n['id']}: FINDING '{n['finding']}' not in {FINDING_VALUES}")
    return nodes, errors


def derive(nodes: dict[str, dict]) -> None:
    for n in nodes.values():
        n["children"] = sorted((c["id"] for c in nodes.values() if c["parent"] == n["id"]),
                               key=sort_key)
        if n["children"] and n["kind"] == "task":
            n["kind"] = "group"
            n["promoted"] = True

    def own_state(n: dict) -> str:
        if n["status"] == "done" and (not n["finding"] or not n["has_read_section"]):
            return "INCOMPLETE"
        return n["status"]

    memo: dict[str, str] = {}

    def state(nid: str) -> str:
        if nid in memo:
            return memo[nid]
        n = nodes[nid]
        s = own_state(n)
        if n["children"]:
            kids = [state(c) for c in n["children"]]
            # a group is done only when every child is done AND its own synthesis is done
            if n["status"] == "blocked" or "blocked" in kids:
                s = "blocked"
            elif all(k == "done" for k in kids) and own_state(n) == "done":
                s = "done"
            elif all(k == "todo" for k in kids) and n["status"] == "todo":
                s = "todo"
            else:
                s = "in-progress"
        memo[nid] = s
        return s

    for nid in nodes:
        state(nid)
    for n in nodes.values():
        s = memo[n["id"]]
        unmet = [d for d in n["depends_on"] if memo.get(d) != "done"]
        # a group's own synthesis waits on its unfinished children
        unmet += [c for c in n["children"] if memo.get(c) != "done"]
        if s == "todo":
            s = "waiting" if unmet else "ready"
        n["state"] = s
        n["waiting_on"] = unmet
        n["depth"] = n["id"].count(".")
        leaves = leaf_ids(nodes, n["id"])
        n["leaves_total"] = len(leaves)
        n["leaves_done"] = sum(memo[x] == "done" for x in leaves)
        n["severity_total"] = {s_: sum(nodes[x]["severity"][s_] for x in subtree(nodes, n["id"]))
                               for s_ in SEVERITIES}


def subtree(nodes: dict, nid: str) -> list[str]:
    out = [nid]
    for c in nodes[nid]["children"]:
        out += subtree(nodes, c)
    return out


def leaf_ids(nodes: dict, nid: str) -> list[str]:
    return [x for x in subtree(nodes, nid) if not nodes[x]["children"]]


def sort_key(nid: str) -> list:
    return [(0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"[.]", nid)]


def cycles(nodes: dict) -> list[str]:
    colour: dict[str, int] = {}
    bad: list[str] = []

    def visit(n: str, stack: list[str]) -> None:
        colour[n] = 1
        for d in nodes[n]["depends_on"]:
            if colour.get(d) == 1:
                bad.append(" -> ".join(stack + [n, d]))
            elif colour.get(d) is None:
                visit(d, stack + [n])
        colour[n] = 2

    for n in nodes:
        if n not in colour:
            visit(n, [])
    return bad


def write_status(nodes: dict, generated: str) -> str:
    leaves = [n for n in nodes.values() if not n["children"]]
    done = sum(n["state"] == "done" for n in leaves)
    sev = {s: sum(n["severity"][s] for n in nodes.values()) for s in SEVERITIES}
    lines = [
        "# GMST checkpoint-1 review — status",
        "",
        "**Generated by `graph.py` — do not edit by hand.** " + generated,
        "",
        f"**{done} of {len(leaves)} leaf nodes done.** Findings so far: "
        f"{sev['blocking']} blocking, {sev['serious']} serious, {sev['minor']} minor.",
        "",
        "| | Node | Stage | Agent | Model | Depends on | State | Findings (b/s/m) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    mark = {"done": "[x]", "in-progress": "[~]", "blocked": "[!]", "ready": "[ ]",
            "waiting": "[.]", "INCOMPLETE": "[?]"}
    order = sorted(nodes.values(), key=lambda n: (STAGES.index(n["stage"]), sort_key(n["id"])))
    for n in order:
        indent = "&nbsp;&nbsp;" * n["depth"]
        t = n["severity_total"]
        lines.append(
            f"| {mark.get(n['state'], '[ ]')} | {indent}**{n['id']}** {n['title']}"
            f"{' *(group)*' if n['children'] else ''} | {STAGE_LABEL[n['stage']]} | {n['agent']} | "
            f"{n['model']} | {', '.join(n['depends_on']) or '-'} | {n['state']} | "
            f"{t['blocking']}/{t['serious']}/{t['minor']} |")
    ready = [n for n in order if n["state"] == "ready" and not n["children"]]
    lines += ["", "## Can start now", ""]
    lines += [f"- `{n['file']}` — {n['title']} ({n['agent']}, {n['model']})" for n in ready] or ["- nothing"]
    waiting = [n for n in order if n["state"] == "waiting"]
    lines += ["", "## Waiting", ""]
    lines += [f"- **{n['id']}** waits on {', '.join(n['waiting_on'])}" for n in waiting] or ["- nothing"]
    lines += ["", "`[x]` done · `[~]` in progress · `[ ]` ready · `[.]` waiting · `[!]` blocked · "
              "`[?]` claims done, FINDING or read/measured section missing", ""]
    return "\n".join(lines)


def main() -> int:
    nodes, errors = load()
    errors += [f"dependency cycle: {c}" for c in cycles(nodes)] if not errors else []
    if errors:
        print("graph.py: the node files are inconsistent:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    derive(nodes)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (HERE / "STATUS.md").write_text(write_status(nodes, generated), encoding="utf-8")
    plan = (HERE / "PLAN.md").read_text(encoding="utf-8")
    data = dict(
        generated=generated,
        basis=header(plan, "basis"), branch=header(plan, "branch"),
        stages=[dict(id=s, label=STAGE_LABEL[s]) for s in STAGES],
        nodes=[nodes[k] for k in sorted(nodes, key=sort_key)],
    )
    payload = json.dumps(data, indent=1, ensure_ascii=False)
    (HERE / "graph.json").write_text(payload + "\n", encoding="utf-8")
    template = (HERE / "dashboard.template.html").read_text(encoding="utf-8")
    safe = payload.replace("</", "<\\/")
    (HERE / "dashboard.html").write_text(template.replace("/*GRAPH_DATA*/null", safe), encoding="utf-8")
    leaves = [n for n in nodes.values() if not n["children"]]
    print(f"{len(nodes)} nodes, {sum(n['state'] == 'done' for n in leaves)}/{len(leaves)} leaves done, "
          f"{sum(n['state'] == 'ready' for n in leaves)} ready -> STATUS.md, graph.json, dashboard.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
