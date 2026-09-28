"""R5 probe 5: how many uk clips are needed to separate the four candidates at the leaderboard's
gaps (large-v2 13.72, large-v3 20.53, turbo 22.83, turbo-uk 12.75 % WER)?
Measures per-clip error counts of tiny and small (faster_whisper CPU int8, language pinned 'uk')
on the 60 built uk clips (cleaned CV10), then:
  * overdispersion phi of per-clip errors vs binomial (var(e_i - p n_i) / (p(1-p) n_i)), per model,
  * paired correlation rho of per-clip error rates between the two models,
  * clips needed for a two-sided 95 % / 80 %-power test of a corpus-WER gap, unpaired and paired,
    and the 95 % CI half-width at the current n=60 and the n=4 in scores.json.
Run: HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run --with jiwer python review/checkpoint-1/scripts/R5/p5_sample_size.py
"""
import json, math, random
from pathlib import Path

import jiwer
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from gmst.metrics import normalize_words

D = Path("eval/results/data")
rows = [json.loads(l) for l in (D / "uk.jsonl").read_text().splitlines() if l.strip()]
refs = [" ".join(normalize_words(r["text"])) for r in rows]
nw = np.array([len(r.split()) for r in refs], dtype=float)
E = {}
for size in ("tiny", "small"):
    m = WhisperModel(size, device="cpu", compute_type="int8")
    e = []
    for r, ref in zip(rows, refs):
        a, _ = sf.read(D / r["wav"], dtype="float32")
        segs, _ = m.transcribe(a, language="uk")
        hyp = " ".join(normalize_words(" ".join(s.text for s in segs)))
        o = jiwer.process_words(ref, hyp)
        e.append(o.substitutions + o.deletions + o.insertions)
    E[size] = np.array(e, dtype=float)
    del m
print(f"n clips={len(rows)}, words/clip mean={nw.mean():.2f} sd={nw.std(ddof=1):.2f}")
for k, e in E.items():
    p = e.sum() / nw.sum()
    phi = np.var(e - p * nw, ddof=1) / (p * (1 - p) * nw.mean())
    print(f"{k}: corpus WER={100*p:.2f}%  macro WER={100*np.mean(e/nw):.2f}%  overdispersion phi={phi:.2f}")
    E[k] = (e, p, phi)
rho = np.corrcoef(E["tiny"][0] / nw, E["small"][0] / nw)[0, 1]
phi = max(E["tiny"][2], E["small"][2])
print(f"paired per-clip correlation rho(tiny, small) = {rho:.2f}; using phi={phi:.2f}")

z = 1.959964 + 0.841621  # 95 % two-sided, 80 % power
wbar = nw.mean()
def var_clip(p):  # variance of per-clip (e_i - p n_i) / wbar, i.e. per-clip contribution to corpus WER
    return phi * p * (1 - p) / wbar
def n_needed(p1, p2, r):
    v = var_clip(p1) + var_clip(p2) - 2 * r * math.sqrt(var_clip(p1) * var_clip(p2))
    return math.ceil(z * z * v / (p1 - p2) ** 2)
LB = {"turbo-uk": .1275, "large-v2": .1372, "large-v3": .2053, "turbo": .2283}
pairs = [("turbo-uk", "large-v2"), ("large-v2", "large-v3"), ("large-v3", "turbo"), ("turbo-uk", "large-v3")]
print("pair                     gap   n unpaired  n paired rho=0.5  n paired rho=measured")
for a, b in pairs:
    print(f"{a:>9} vs {b:<10} {100*abs(LB[a]-LB[b]):5.2f}  {n_needed(LB[a],LB[b],0):>10}  "
          f"{n_needed(LB[a],LB[b],0.5):>16}  {n_needed(LB[a],LB[b],rho):>20}")
for n in (4, 60, 200):
    for p in (.1372, .2053):
        print(f"95% CI half-width of corpus WER at n={n}, WER={100*p:.1f}%: +/-{100*1.96*math.sqrt(var_clip(p)/n):.1f} pts")
# bootstrap check of the analytic CI for the measured small model at n=60
rng = random.Random(0); e, p, _ = E["small"]; bs = []
for _ in range(2000):
    idx = [rng.randrange(len(e)) for _ in e]
    bs.append(e[idx].sum() / nw[idx].sum())
lo, hi = np.percentile(bs, [2.5, 97.5])
print(f"bootstrap 95% CI, small, n=60: [{100*lo:.1f}, {100*hi:.1f}] around {100*p:.1f}")
