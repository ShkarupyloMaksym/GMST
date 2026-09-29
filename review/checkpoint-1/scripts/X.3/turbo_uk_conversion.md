# turbo-uk (Yehor/whisper-large-v3-turbo-quantized-uk) CTranslate2 conversion attempt

Commands run 2026-09-29, network used only to fetch this one repo (per node authorization).

## 1. Repo format (HF API, no download needed)

```
$ curl -sL https://huggingface.co/api/models/Yehor/whisper-large-v3-turbo-quantized-uk
```
`"quantization_config":{"config_groups":{"group_0":{"targets":["Linear"],"weights":{"num_bits":4}}},"format":"pack-quantized","quant_method":"compressed-tensors"}`
`"architectures":["WhisperForConditionalGeneration"]`, siblings include `model.safetensors`,
`config.json` — an HF-transformers checkpoint, 4-bit `compressed-tensors` quantized, not
CTranslate2. Confirms "not CTranslate2-loadable" as-is (no `model.bin`/`vocabulary.json` etc.).

## 2. Download (snapshot_download, offline rule lifted for this repo only)

`uv run python -c "from huggingface_hub import snapshot_download; snapshot_download('Yehor/whisper-large-v3-turbo-quantized-uk')"`
→ succeeded, 13 files, `model.safetensors` 537 MB, cached at
`~/.cache/huggingface/hub/models--Yehor--whisper-large-v3-turbo-quantized-uk`.

## 3. ct2-transformers-converter attempt

```
$ uv run ct2-transformers-converter --model Yehor/whisper-large-v3-turbo-quantized-uk \
    --output_dir eval/results/models/whisper-large-v3-turbo-quantized-uk-ct2 --quantization int8
```
```
Traceback (most recent call last):
  ...
  File ".../ctranslate2/converters/transformers.py", line 107, in _load
    with torch.no_grad():
         ^^^^^
NameError: name 'torch' is not defined
```

Cause: `torch` is not installed in `.venv` (`ModuleNotFoundError: No module named 'torch'`,
confirmed directly). ctranslate2 4.8.1's `converters/transformers.py` line 11 does
`try:\n    import torch\n` (no visible `except` clause printed by `inspect.getsource`, i.e. the
import is silently swallowed somewhere in that block) — the converter never raises "install
torch", it dies later with an unrelated `NameError`. `torch` is not a GMST dependency (`CLAUDE.md`:
"mlx_whisper... pulls torch and is slow-moving" — the project avoids it on purpose). Separately,
the checkpoint's own quantization (`compressed-tensors`, `pack-quantized`, 4-bit) needs the
`compressed_tensors` package to dequantize on load in `transformers`
(`ModuleNotFoundError: No module named 'compressed_tensors'`, confirmed directly), and
ctranslate2's `transformers.py` quantization-config branch only special-cases
`quantization_config.quant_method == "awq"` (grepped: every other `quant_method` falls through to
`quantization_config.group_size` / `.bits`, attributes the compressed-tensors config object does
not have) — so even with `torch` present, conversion has no support path for this checkpoint's
quantization format.

## Conclusion

Converting turbo-uk to CTranslate2 needs `torch` + `compressed_tensors` installed (outside this
node's network authorization, which was scoped to downloading the two turbo model repos, not
installing packages into the shared `.venv` other agents are concurrently using) and, even then,
ctranslate2 4.8.1 has no converter code path for `compressed-tensors`-format quantization — it
would first need dequantizing to a plain fp16/fp32 HF checkpoint by some other tool, which is
outside this node's scope. **turbo-uk is not evaluated in X.3** (recorded as blocking, not fixed).
