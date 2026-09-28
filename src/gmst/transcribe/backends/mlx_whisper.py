"""MLX Whisper backend — Apple Silicon fast path (Apple GPU).

Untested on CI (MLX will not import on Linux). ``model_repo`` must be an mlx path, e.g.
``mlx-community/whisper-large-v3-turbo``. ``detect_language`` costs one extra encoder pass and is
counted in the latency budget. Per-segment LID goes through the same ``resolve_language`` (uk/ru
tie-break + sticky threshold) as the faster-whisper backend.
"""

from __future__ import annotations

import numpy as np

from gmst.audio.types import SAMPLE_RATE, AudioArray
from gmst.config import Config
from gmst.transcribe.lid import resolve_language
from gmst.transcribe.types import Segment, Word

_DEFAULT_REPO = {
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "small": "mlx-community/whisper-small-mlx",
}


class MlxWhisperEngine:
    def __init__(
        self, cfg: Config, *, per_segment_lid: bool = True, word_timestamps: bool | None = None
    ):
        import mlx_whisper  # noqa: F401  (import-time check that the backend is available)

        self._cfg = cfg
        self._per_segment_lid = per_segment_lid
        self._word_ts = cfg.word_timestamps if word_timestamps is None else word_timestamps
        self._repo = cfg.model_repo or _DEFAULT_REPO.get(cfg.model_size)
        if not self._repo:
            raise ValueError(
                f"no known mlx repo for model_size={cfg.model_size!r}; set model_repo explicitly"
            )
        self._model = None
        # Load now, not at the first utterance: a missing repo must fail at startup, where
        # load_engine turns it into ModelUnavailable / exit 2, and bench must time the real load
        # (R2 F6). _load() fills mlx_whisper's own ModelHolder cache, so transcribe() reuses it.
        self._load()

    def transcribe(
        self,
        audio: AudioArray,
        *,
        language: str | None = None,
        prompt: str | None = None,
    ) -> list[Segment]:
        import mlx_whisper

        audio = np.ascontiguousarray(audio, dtype=np.float32)
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self._repo,
            language=language,
            initial_prompt=prompt,
            word_timestamps=self._word_ts,
        )
        out: list[Segment] = []
        prev_lang = language
        for s in result.get("segments", []):
            if language is not None:
                lang, prob = language, 1.0
            elif self._per_segment_lid:
                lang, prob = self._detect_slice(audio, s["start"], s["end"], prev_lang)
            else:
                lang, prob = result.get("language", "en"), 1.0
            prev_lang = lang
            words = [
                Word(str(w["word"]).strip(), float(w["start"]), float(w["end"]))
                for w in s.get("words", [])
            ]
            out.append(
                Segment(float(s["start"]), float(s["end"]), s["text"], lang,
                        is_final=False, lid_prob=prob, words=words)
            )
        return out

    def detect_language(
        self, audio: AudioArray, *, prev_lang: str | None = None
    ) -> tuple[str, float]:
        raw_lang, raw_prob, all_probs = self._detect_full(audio)
        return resolve_language(
            raw_lang,
            raw_prob,
            all_probs,
            prev_lang=prev_lang,
            threshold=self._cfg.lid_threshold,
            tiebreak_margin=self._cfg.lid_tiebreak_margin,
            allowed=self._cfg.lid_languages,
        )

    def _detect_slice(
        self, audio: AudioArray, start: float, end: float, prev_lang: str | None
    ) -> tuple[str, float]:
        """LID for one segment, on a window around it — never on the whole buffer.

        A short interjection used to fall back to the entire ``audio``, whose first 30 s is all the
        detector looks at: a Ukrainian aside late in a long file got the opening's language.
        """
        min_n = SAMPLE_RATE // 2
        a = int(max(0.0, start) * SAMPLE_RATE)
        b = min(len(audio), int(end * SAMPLE_RATE))
        if b - a < min_n:  # widen symmetrically, clamped to the buffer
            pad = (min_n - (b - a) + 1) // 2
            a, b = max(0, a - pad), min(len(audio), b + pad)
            if b - a < min_n:  # ran into an edge — take the shortfall from the other side
                if a == 0:
                    b = min(len(audio), min_n)
                else:
                    a = max(0, b - min_n)
        return self.detect_language(audio[a:b], prev_lang=prev_lang)

    def _load(self):
        """The model used for LID — the *same* instance ``mlx_whisper.transcribe`` caches.

        Loading it separately would keep two copies of a large-v3-class model in unified memory
        (and ``load_model``'s default dtype is float32).
        """
        if self._model is None:
            import mlx.core as mx
            from mlx_whisper.transcribe import ModelHolder

            self._model = ModelHolder.get_model(self._repo, mx.float16)
        return self._model

    def _detect_full(self, audio: AudioArray) -> tuple[str, float, list[tuple[str, float]]]:
        import mlx_whisper.audio as mwa
        import mlx_whisper.decoding as mwd

        model = self._load()
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        mel = mwa.log_mel_spectrogram(mwa.pad_or_trim(audio), model.dims.n_mels)
        _, probs = mwd.detect_language(model, mel[None])
        dist = list(probs[0].items())
        lang = max(dist, key=lambda kv: kv[1])[0]
        return lang, float(probs[0][lang]), dist
