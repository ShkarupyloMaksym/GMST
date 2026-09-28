"""faster-whisper backend (CTranslate2). Portable default; CPU int8 on Apple Silicon.

LID: ``detect_language`` uses the model's own detector (one encoder pass), restricted to
``cfg.lid_languages`` by ``resolve_language``. When ``transcribe`` is called with ``language=None``
and ``per_segment_lid`` is on, each returned segment is only *labelled* by running the detector on a
window around it — the text is still faster-whisper's single autodetected language (R2 F3). Neither
pipeline relies on that any more: batch decodes each VAD region in its detected language
(``pipeline.batch.transcribe_by_region``) and the stream passes an explicit ``language``.

``multilingual=True`` would make faster-whisper run its *own* per-segment LID inside the decode
pass, but it has no uk/ru tie-break and 1.2.1 exposes no per-segment ``language`` to read back — so
it is only asked for when ``per_segment_lid`` is off, and we never pay for both.
"""

from __future__ import annotations

import numpy as np

from gmst.audio.types import SAMPLE_RATE, AudioArray
from gmst.config import Config
from gmst.transcribe.lid import resolve_language
from gmst.transcribe.types import Segment, Word


class FasterWhisperEngine:
    def __init__(
        self,
        cfg: Config,
        *,
        per_segment_lid: bool = True,
        vad_filter: bool = False,
        word_timestamps: bool | None = None,
    ):
        from faster_whisper import WhisperModel

        self._cfg = cfg
        self._per_segment_lid = per_segment_lid
        self._vad_filter = vad_filter
        self._word_ts = cfg.word_timestamps if word_timestamps is None else word_timestamps
        self._model = WhisperModel(
            cfg.model_repo or cfg.model_size,
            device=cfg.compute_device,
            compute_type=cfg.compute_type,
        )

    def transcribe(
        self,
        audio: AudioArray,
        *,
        language: str | None = None,
        prompt: str | None = None,
    ) -> list[Segment]:
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        fw_segments, info = self._model.transcribe(
            audio,
            language=language,
            multilingual=language is None and not self._per_segment_lid,
            initial_prompt=prompt,
            vad_filter=self._vad_filter,
            word_timestamps=self._word_ts,
            language_detection_threshold=self._cfg.lid_threshold,
        )
        out: list[Segment] = []
        prev_lang = language
        for s in fw_segments:
            if language is not None:
                lang, prob = language, 1.0
            elif self._per_segment_lid:
                lang, prob = self._detect_slice(audio, s.start, s.end, prev_lang)
            else:
                lang, prob = info.language, float(info.language_probability)
            prev_lang = lang
            words = [
                Word(w.word.strip(), float(w.start), float(w.end)) for w in (s.words or [])
            ]
            out.append(
                Segment(
                    float(s.start), float(s.end), s.text, lang,
                    is_final=False, lid_prob=prob, words=words,
                )
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

    def _detect_full(self, audio: AudioArray) -> tuple[str, float, list[tuple[str, float]]]:
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        lang, prob, all_probs = self._model.detect_language(audio)
        return lang, float(prob), list(all_probs or [])

    def _detect_slice(
        self, audio: AudioArray, start: float, end: float, prev_lang: str | None
    ) -> tuple[str, float]:
        """LID for one segment, on a window around it — never on the whole file.

        A short interjection used to fall back to ``audio``, and ``detect_language`` only looks at
        the first 30 s of what it is handed: a Ukrainian aside at minute 8 would be labelled with
        the language the recording opened in. Widen the window instead of abandoning it.
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
