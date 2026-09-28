# Test fixtures

Needed for the language-ID tests (Phase 1):

- `en.wav` — ~5 s of clear English speech, 16 kHz mono
- `uk.wav` — ~5 s of clear Ukrainian speech, 16 kHz mono

Keep them short and commit them. Public-domain / self-recorded only. Tests that load a real ASR
model are marked `@pytest.mark.slow` and are deselected by default.
