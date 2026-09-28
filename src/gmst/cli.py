"""Command-line entry point.

``main()`` loads ``Config`` and hands it to every subcommand, so the defaults < ``gmst.toml`` <
``GMST_*`` precedence chain is live.

Exit codes: ``0`` success, ``1`` bad input (no such file / device), ``2`` the model or backend is
unavailable (with the "run ``gmst warmup``" hint), ``3`` the input device disappeared mid-session.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from gmst.config import Config

Handler = Callable[[argparse.Namespace, Config], int]


def _load_engine_or_report(cfg: Config, **kwargs):
    """``load_engine`` with the two documented failures turned into an exit-2 message."""
    from gmst.transcribe.backends import ModelUnavailable, load_engine

    try:
        return load_engine(cfg, **kwargs)
    except (ModelUnavailable, NotImplementedError) as exc:
        print(exc, file=sys.stderr)
        return None


def _cmd_devices(args: argparse.Namespace, cfg: Config) -> int:
    try:
        import sounddevice as sd
    except OSError as exc:  # missing PortAudio system library
        print(f"cannot load PortAudio: {exc}", file=sys.stderr)
        return 1

    default_in, _ = sd.default.device
    hostapis = sd.query_hostapis()
    print(f"{'idx':>4}  {'ch':>2}  {'rate':>7}  host / name")
    print("-" * 60)
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] < 1:
            continue
        host = hostapis[dev["hostapi"]]["name"]
        mark = "*" if idx == default_in else " "
        print(
            f"{idx:>4}{mark} {dev['max_input_channels']:>2}  "
            f"{dev['default_samplerate']:>7.0f}  {host} / {dev['name']}"
        )
    print("\n* = system default input")
    return 0


def _cmd_warmup(args: argparse.Namespace, cfg: Config) -> int:
    import numpy as np

    target = cfg.model_repo or cfg.model_size
    print(f"loading {cfg.engine} / {target} …", file=sys.stderr)
    engine = _load_engine_or_report(cfg, per_segment_lid=False)
    if engine is None:
        return 2
    engine.transcribe(np.zeros(16_000, dtype=np.float32))  # force weights to download/init
    print("ready", file=sys.stderr)
    return 0


def _cmd_batch(args: argparse.Namespace, cfg: Config) -> int:
    from gmst.pipeline.batch import run_batch
    from gmst.sink.base import make_sink

    if not Path(args.input).is_file():
        print(f"no such file: {args.input}", file=sys.stderr)
        return 1
    engine = _load_engine_or_report(cfg)
    if engine is None:
        return 2
    sink = make_sink(cfg, args.out)
    result = run_batch(args.input, cfg, engine, sink)
    print(
        f"\n{result.n_segments} segments · {result.audio_seconds:.1f}s audio · "
        f"{result.transcribe_seconds:.1f}s transcribe · RTF {result.rtf:.3f}",
        file=sys.stderr,
    )
    return 0


def _meter(dbfs: float, width: int = 30, floor: float = -60.0) -> str:
    frac = 0.0 if dbfs == float("-inf") else max(0.0, min(1.0, (dbfs - floor) / -floor))
    filled = round(frac * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _cmd_listen(args: argparse.Namespace, cfg: Config) -> int:
    from gmst.audio.device_source import DeviceSource
    from gmst.audio.types import rms_dbfs

    try:
        src = DeviceSource(cfg, device=args.device).open()
    except (OSError, ValueError) as exc:
        print(f"cannot open input: {exc}", file=sys.stderr)
        return 1

    print(
        f"listening on '{src.device_label}' @ {src.in_rate} Hz → 16 kHz — Ctrl-C to stop",
        file=sys.stderr,
    )
    try:
        for block in src.blocks():
            db = rms_dbfs(block)
            st = src.stats
            extra = ""
            if st.overflows:
                extra += f" overflow={st.overflows}"
            if st.blocks_dropped:
                extra += f" dropped={st.blocks_dropped} [lagging]"
            db_txt = " -inf" if db == float("-inf") else f"{db:6.1f}"
            print(f"\r{_meter(db)} {db_txt} dBFS{extra}   ", end="", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        src.close()
        print(file=sys.stderr)
    return 0


def _cmd_bench(args: argparse.Namespace, cfg: Config) -> int:
    from gmst.bench import format_table, run_bench

    if not Path(args.clip).is_file():
        print(f"no such file: {args.clip}", file=sys.stderr)
        return 1
    reference = Path(args.ref).read_text(encoding="utf-8") if args.ref else None
    try:
        rows = run_bench(args.clip, cfg, reference)
    except NotImplementedError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"engine={cfg.engine}  clip={args.clip}  max_buffer_seconds={cfg.max_buffer_seconds}\n")
    print(format_table(rows))
    return 0


def _cmd_stream(args: argparse.Namespace, cfg: Config) -> int:
    import signal
    import threading

    from gmst.audio.device_source import DeviceLost, DeviceSource
    from gmst.pipeline.stream import run_stream
    from gmst.sink.base import make_sink

    try:
        source = DeviceSource(cfg, device=args.device).open()
    except (OSError, ValueError) as exc:
        print(f"cannot open input: {exc}", file=sys.stderr)
        return 1

    engine = _load_engine_or_report(cfg, per_segment_lid=False)  # the pipeline runs its own LID
    if engine is None:
        source.close()
        return 2

    if args.sse_port is not None:  # `--sse-port 0` means "any free port", not "unset"
        cfg = replace(cfg, sse_port=args.sse_port)

    fired = False

    def _on_sigint(signum, frame):
        nonlocal fired
        if fired:  # a second Ctrl-C: stop waiting for the final decode
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            raise KeyboardInterrupt
        fired = True
        print("\nstopping — flushing the final utterance…", file=sys.stderr)
        source.close()  # drain -> flush -> close

    sink = make_sink(cfg, args.out, override=args.sink)
    prev_handler = None
    started = False
    try:
        if args.sink == "sse" or (args.sink is None and cfg.sink == "sse"):
            print(f"SSE: http://127.0.0.1:{sink.port}/  (events at /events)", file=sys.stderr)
        # signal.signal only works on the main thread; guard rather than assume
        if threading.current_thread() is threading.main_thread():
            prev_handler = signal.signal(signal.SIGINT, _on_sigint)

        lang = args.language or cfg.language or "auto"
        print(
            f"streaming from '{source.device_label}' @ {source.in_rate} Hz · lang={lang}"
            " — Ctrl-C to stop",
            file=sys.stderr,
        )
        started = True
        stats = run_stream(cfg, source, engine, sink, language=args.language or cfg.language)
    except DeviceLost as exc:
        print(f"\naudio input lost: {exc}", file=sys.stderr)
        return 3
    finally:
        if prev_handler is not None:
            signal.signal(signal.SIGINT, prev_handler)
        source.close()  # never leave the PortAudio stream open behind an error
        if not started:
            sink.close()  # once run_stream starts it owns the sink and closes it itself

    print(
        f"\n{stats.utterances} utterances · {stats.decodes} decodes · "
        f"{stats.committed_words} words committed",
        file=sys.stderr,
    )
    return 0


def _stub(phase: str) -> Handler:
    def run(args: argparse.Namespace, cfg: Config) -> int:
        print(f"not implemented yet — see PLAN.md ({phase})", file=sys.stderr)
        return 2

    return run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gmst", description="Speech-to-text for Google Meet")
    p.add_argument("-c", "--config", metavar="PATH", help="path to a gmst.toml")
    sub = p.add_subparsers(dest="command", required=True)

    devices = sub.add_parser("devices", help="list audio input devices")
    devices.set_defaults(func=_cmd_devices)

    warmup = sub.add_parser("warmup", help="pre-download / initialise the configured model")
    warmup.set_defaults(func=_cmd_warmup)

    bench = sub.add_parser("bench", help="measure RTF / streaming amplification / WER per model")
    bench.add_argument("clip", help="hand-transcribed bilingual audio clip")
    bench.add_argument("--ref", help="reference transcript file, for WER")
    bench.set_defaults(func=_cmd_bench)

    batch = sub.add_parser("batch", help="transcribe an audio file")
    batch.add_argument("input", help="audio file (decoded via PyAV)")
    batch.add_argument("-o", "--out", help="output path; .srt/.vtt/.jsonl/.txt pick the sink")
    batch.set_defaults(func=_cmd_batch)

    listen = sub.add_parser("listen", help="show a live input level meter")
    listen.add_argument("-d", "--device", help="input device id or name substring")
    listen.set_defaults(func=_cmd_listen)

    stream = sub.add_parser("stream", help="live transcription of an input device")
    stream.add_argument("-d", "--device", help="input device id or name substring")
    stream.add_argument("-o", "--out", help="output path; .srt/.vtt/.jsonl/.txt pick the sink")
    stream.add_argument(
        "--language",
        choices=["en", "uk"],
        help="pin the language and skip per-utterance detection",
    )
    stream.add_argument(
        "--sink", choices=["console", "jsonl", "srt", "sse"], help="override the configured sink"
    )
    stream.add_argument("--sse-port", type=int, help="port for --sink sse (default from config)")
    stream.set_defaults(func=_cmd_stream)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load(Path(args.config) if args.config else None)
    return args.func(args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
