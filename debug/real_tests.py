"""
debug/real_tests.py — real pytest test runner, same check(file_path) ->
bool interface as fake_tests.py, so blast_radius.py can swap between them
with one line changed.

Convention: for demo_repo/auth/jwt_auth.py, looks for a test file at
demo_repo/tests/test_jwt_auth.py (i.e. demo_repo/tests/test_<stem>.py).
This convention doesn't exist yet -- no test files have been written for
demo_repo. Once they are, point blast_radius.py at `check` from this
module instead of fake_tests.

If no test file exists for a given source file, this returns None (not
True/False) -- "we don't know" is a different, more honest answer than
silently guessing pass or fail, and callers should treat None as
"no coverage, can't verify" rather than "didn't break."
"""

import subprocess
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent
TESTS_DIRNAME = "tests"


def _test_path_for(file_path: str) -> Optional[Path]:
    """demo_repo/auth/jwt_auth.py -> demo_repo/tests/test_jwt_auth.py"""
    p = Path(file_path)
    stem = p.stem
    # demo_repo/<...>/<stem>.py -> demo_repo/tests/test_<stem>.py
    repo_relative_root = p.parts[0]  # "demo_repo"
    candidate = REPO_ROOT / repo_relative_root / TESTS_DIRNAME / f"test_{stem}.py"
    return candidate if candidate.exists() else None


def check(file_path: str) -> Optional[bool]:
    """Return True if the matching test file fails (file is broken),
    False if it passes, or None if there's no test file to check against."""
    test_path = _test_path_for(file_path)
    if test_path is None:
        print(f"[real_tests] {file_path}: no test file found (looked for tests/test_<name>.py) -- can't verify")
        return None

    result = subprocess.run(
        ["python", "-m", "pytest", str(test_path), "-q"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    broke = result.returncode != 0
    print(f"[real_tests] {file_path}: {'BROKEN' if broke else 'passed'} (via {test_path.relative_to(REPO_ROOT)})")
    if broke:
        print(result.stdout[-1500:])
    return broke
