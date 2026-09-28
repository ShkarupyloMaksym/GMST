"""R5 probe 6: what `gmst.metrics.normalize_words` does to the cases where Whisper output and the
cleaned-CV10 reference differ in *form* rather than content.
Run: uv run python review/checkpoint-1/scripts/R5/p6_normalization.py
"""
import csv, re
from gmst.metrics import normalize_words, word_error_rate

cases = [
    ("в'яткою", "вʼяткою"), ("в'яткою", "в’яткою"),
    ("у тисяча дев'ятсот двадцятому році", "у 1920 році"),
    ("двадцять п'ять відсотків", "25%"),
    ("що-небудь", "що небудь"),
    ("Київ — столиця", "київ столиця"),
    ("ґанок", "ганок"),
]
for ref, hyp in cases:
    print(f"ref={ref!r:40} hyp={hyp!r:30} -> {normalize_words(hyp)}  WER={word_error_rate(ref, hyp):.2f}")
rows = list(csv.DictReader(open("eval/results/cv10-uk-testset-clean/labels_relative.csv", encoding="utf-8")))
print("reference rows containing a digit:", sum(bool(re.search(r"\d", r["text"])) for r in rows), "of", len(rows))
