"""R1 probe: a punctuation-only token (normalizes to "") never agrees, so nothing past it commits
until the stall machinery force-flushes.

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R1/probe_punct_token.py
"""
from gmst.reconcile import LocalAgreement

la = LocalAgreement()
h = ["Так", "-", "звісно,", "давайте"]
for i in range(4):
    print(i, la.push(h + ["далі"] * i), "stalled_pushes =", la.stalled_pushes)
