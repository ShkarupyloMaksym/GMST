"""R3 probe: PLAN.md's failure-mode row is titled "Ctrl-C / SIGTERM" — does `gmst stream` actually
trap SIGTERM the same way it traps SIGINT?

`src/gmst/cli.py::_cmd_stream` only ever calls
    signal.signal(signal.SIGINT, _on_sigint)
There is no `signal.signal(signal.SIGTERM, ...)` anywhere in the codebase (grep confirms it).

This spawns a child process that reproduces the exact idiom in `_cmd_stream`: register a SIGINT
handler that does a "drain -> flush -> close" (here: prints CLEANUP-RAN and exits 0), loop reading
blocks like `source.blocks()` does, and rely on Python's default disposition for every other
signal. It then sends SIGTERM and shows the child dies without running its cleanup path — i.e.
without the "flush the uncommitted tail as final" step `run_stream`'s `finally` block performs.

Run: uv run python review/checkpoint-1/scripts/R3/sigterm_probe.py
"""
import signal
import subprocess
import sys
import time

CHILD = r"""
import signal, sys, time

def _on_sigint(signum, frame):
    print("CLEANUP-RAN", flush=True)
    sys.exit(0)

signal.signal(signal.SIGINT, _on_sigint)   # exactly what cli.py._cmd_stream does; no SIGTERM handler
print("READY", flush=True)
while True:
    time.sleep(0.05)
"""


def run_case(sig: signal.Signals) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD], stdout=subprocess.PIPE, text=True,
    )
    line = proc.stdout.readline().strip()
    assert line == "READY", line
    time.sleep(0.2)
    proc.send_signal(sig)
    try:
        out, _ = proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
    print(f"signal={sig.name} exit_code={proc.returncode} stdout_after_signal={out!r}")


if __name__ == "__main__":
    run_case(signal.SIGINT)
    run_case(signal.SIGTERM)
