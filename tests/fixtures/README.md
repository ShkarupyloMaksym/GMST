# Test fixtures

Used by the language-ID tests (`tests/test_lid_fixtures_slow.py`, `@pytest.mark.slow`):

- `en.wav` — 3.8 s of English, 16 kHz mono: LibriSpeech test-clean `260-123440-0014`
  ("And I declare it's too bad that it is"). LibriSpeech is CC BY 4.0 (Panayotov et al., 2015),
  from LibriVox public-domain recordings.
- `uk.wav` — 4.8 s of Ukrainian, 16 kHz mono: Common Voice 10 `uk` test clip `2023`, via the
  cleaned test set `egorsmkv/cv10-uk-testset-clean` ("хто попікся окропом на воду дує"). Common
  Voice is CC0. Whisper's raw detector labels this clip **Russian** (review R2), so it pins the
  `lid_languages` fold of `ru` into `uk`.

Both were copied from `eval/results/data/` (built by `eval/build_sets.py`) during the 2026-09-28
review (F.5). Keep them short. Tests that load a real ASR model are deselected by default.
