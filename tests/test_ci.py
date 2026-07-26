"""CI assertion wrapper: keyless deterministic demo run.

Runs `python main.py --reset` with an empty OPENAI_API_KEY and asserts
frozen fresh-state output. Only time-invariant lines are asserted:
ingestion counts, the two deliberately backdated check counts, total
leads, and the deterministic analysis source. Age-threshold counts
(stuck escalations, aging metrics, recommendation count) depend on the
frozen dataset's absolute timestamps drifting against wall-clock time
and are deliberately NOT asserted. No dates, timestamps, or durations.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_S = 300

# Frozen 2026-07-27 from piped fresh-clone runs, Python 3.12.0 and
# 3.14.4: two identical runs + one PYTHONHASHSEED-varied run per
# interpreter, output identical modulo logger wall-clock prefixes.
FROZEN_LINES = [
    "[SEED] Ingested: 74 | Duplicates: 1 | Conflicts: 1 | Failed: 0",
    "  Follow-up escalations: 1",
    "  Reengagement queued:   1",
    "  Total leads:          74",
    "Source: deterministic",
    "[DONE] Demo run complete.",
]


def test_keyless_demo_deterministic():
    env = dict(os.environ, OPENAI_API_KEY="")
    r = subprocess.run(
        [sys.executable, "main.py", "--reset"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=TIMEOUT_S,
    )
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stdout}\n{r.stderr}"
    for frozen in FROZEN_LINES:
        assert frozen in r.stdout, f"missing frozen line: {frozen!r}"
