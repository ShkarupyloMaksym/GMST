"""Write the fixed clip list for X.2 (60 en + 60 uk, manifest/sorted order)."""
import glob
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clips.txt")

en = sorted(glob.glob(os.path.join(ROOT, "eval/results/data/en/*.wav")))
uk = sorted(glob.glob(os.path.join(ROOT, "eval/results/data/uk/*.wav")))

assert len(en) == 60, len(en)
assert len(uk) == 60, len(uk)

with open(OUT, "w") as f:
    for p in en:
        f.write(f"en\t{p}\n")
    for p in uk:
        f.write(f"uk\t{p}\n")

print(f"wrote {OUT} with {len(en)} en + {len(uk)} uk clips")
