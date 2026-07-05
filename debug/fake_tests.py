"""
debug/fake_tests.py — scripted pass/fail test runner for the blast-radius
demo.

demo_repo has no real test suite yet, so "run pytest for real" would just
report "no tests collected" for every dependent -- not a useful demo, and
not because the mechanism is wrong, just because there's nothing to run.
This is the explicit fallback the build plan calls for in section 7:
"a scripted fake_tests.py that deterministically returns pass/fail for
the 2-3 files you've pre-decided will 'break' -- still honest about the
mechanism, just not running a real test suite live."

IMPORTANT: this is a stand-in, not the real verification step. It exists
so debug/blast_radius.py has something to call right now. Swap in
debug/real_tests.py (real pytest execution) the moment you have actual
test files under demo_repo/tests/ -- blast_radius.py takes a test_runner
callable specifically so this swap is a one-line change, not a rewrite.

Edit SCRIPTED_RESULTS below to match whatever changed_file you're
demoing against.
"""

from typing import Optional

# file_path (relative, e.g. "demo_repo/auth/jwt_auth.py") -> "did it break?"
# Anything not listed here defaults to False (didn't break) -- see
# DEFAULT_RESULT. This mirrors the plan's demo script: a handful of real
# dependents, only some of which actually break.
# This matches an actual applied change: db.py's Database.get() was
# renamed to get_by_id(). Every file below that calls db.get(...) is
# genuinely broken (confirmed via smoke_test.py -- AttributeError).
# auth/jwt_auth.py (uses db.find_by) and notifications/notifier.py (uses
# db.insert / db.tables[...].get(), a dict method, not Database.get())
# are real dependents of db.py but NOT broken by this specific change --
# left at the DEFAULT_RESULT of False below, which is the point: not
# every dependent breaks on every change.
SCRIPTED_RESULTS = {
    "demo_repo/auth/dependencies.py": True,
    "demo_repo/crud/projects.py": True,
    "demo_repo/crud/tasks.py": True,
    "demo_repo/crud/comments.py": True,
    "demo_repo/auth/jwt_auth.py": False,
    "demo_repo/notifications/notifier.py": False,
}

DEFAULT_RESULT = False


def check(file_path: str) -> bool:
    """Return True if `file_path` should be treated as broken by the
    current change, per the scripted table above."""
    result = SCRIPTED_RESULTS.get(file_path, DEFAULT_RESULT)
    print(f"[fake_tests] {file_path}: {'BROKEN' if result else 'passed'} (scripted)")
    return result


def set_result(file_path: str, broke: bool) -> None:
    """Convenience for tuning the scripted outcome right before a demo run,
    e.g. from a notebook or a quick CLI flag, without editing this file."""
    SCRIPTED_RESULTS[file_path] = broke
