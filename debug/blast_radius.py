"""
debug/blast_radius.py — Step 4: write path.

When a file changes: find candidate dependents via Cognee's graph,
VERIFY which ones actually broke (don't assume), fix only the real
breakages, then forget() the stale version so it can't resurface as a
distractor later.

Test verification is pluggable (test_runner: str -> bool | None):
  - debug/fake_tests.py (default): scripted pass/fail, since demo_repo
    has no real tests yet. This is the plan's own explicit §7 fallback,
    not a shortcut invented here.
  - debug/real_tests.py: real pytest, ready the moment test files exist
    under demo_repo/<pkg>/tests/test_<name>.py.
Swapping one for the other is the --real-tests flag below, not a
rewrite -- that pluggability is the point.

Dependent-finding reuses the exact recall() configuration validated in
memory/retrieve.py (query_type=SearchType.CHUNKS, only_context=False) --
see that file's docstring for why those specific settings are the ones
that actually carry file provenance through to us.

Usage:
    python debug/blast_radius.py demo_repo/db.py
    python debug/blast_radius.py demo_repo/db.py --real-tests
"""

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Windows fix: see memory/verify_setup.py.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).parent.parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent))

import cognee
from cognee import SearchType
from groq import Groq

import ingest
import retrieve
import fake_tests
import real_tests

REPO_ROOT = Path(__file__).parent.parent
GROQ_MODEL = "llama-3.3-70b-versatile"


async def find_dependents(
    changed_file: str,
    dataset_name: str = ingest.DEFAULT_DATASET,
    session_id: Optional[str] = None,
    top_k: int = 5,
) -> List[str]:
    """Ask Cognee's graph which files depend on changed_file, and map
    the results back to relative file paths via manifest.json."""
    query = f"files that import or depend on {changed_file}"
    recalled = await cognee.recall(
        query_text=query,
        datasets=[dataset_name],
        query_type=SearchType.CHUNKS,
        only_context=False,
        top_k=top_k,
        session_id=session_id,
    )

    manifest = ingest.load_manifest()
    by_data_id = retrieve._manifest_lookup_by_data_id(manifest)

    dependents: List[str] = []
    for entry in recalled:
        _text, data_id = retrieve._extract_text_and_data_id(entry)
        if not data_id or data_id not in by_data_id:
            continue
        file_path = by_data_id[data_id]
        if file_path != changed_file and file_path not in dependents:
            dependents.append(file_path)

    return dependents


def verify_dependents(
    dependents: List[str],
    test_runner=fake_tests.check,
) -> Tuple[List[str], List[dict]]:
    """Run test_runner against every candidate dependent. Returns
    (actually_broken, feedback) where feedback is the ground-truth list
    shaped for cognee.improve()'s feedback_alpha param later. Entries
    where test_runner returns None (no coverage, real_tests.py's honest
    "can't verify") are reported but excluded from feedback -- we don't
    have ground truth for them, so we shouldn't pretend we do."""
    broken: List[str] = []
    feedback: List[dict] = []

    for f in dependents:
        result = test_runner(f)
        if result is None:
            print(f"[skip] {f}: no verification available, not touching it")
            continue
        feedback.append({"element": f, "correct": result})
        if result:
            broken.append(f)

    return broken, feedback


def ask_groq_to_fix(broken_file: str, changed_file: str, client: Groq) -> str:
    """One Groq call: given the current (new) content of changed_file and
    the full content of broken_file, ask for an updated broken_file that's
    compatible again. Returns the fixed file's full new source."""
    changed_content = (REPO_ROOT / changed_file).read_text(encoding="utf-8")
    broken_content = (REPO_ROOT / broken_file).read_text(encoding="utf-8")

    prompt = f"""You are fixing a Python file that broke because one of its dependencies changed.

The dependency, `{changed_file}`, now looks like this:
```python
{changed_content}
```

The dependent file, `{broken_file}`, currently looks like this and is now broken or incompatible:
```python
{broken_content}
```

Return ONLY the complete, fixed source code for `{broken_file}` -- no explanation, no markdown fences, just the raw Python file content, updated to work correctly with the new version of `{changed_file}`. Preserve everything about the file that doesn't need to change."""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    fixed = response.choices[0].message.content.strip()
    # Groq sometimes wraps output in markdown fences despite instructions --
    # strip them defensively rather than writing "```python" into a .py file.
    if fixed.startswith("```"):
        lines = fixed.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        fixed = "\n".join(lines)
    return fixed


def apply_fix(file_path: str, new_content: str) -> None:
    full_path = REPO_ROOT / file_path
    full_path.write_text(new_content, encoding="utf-8")
    print(f"[fixed] wrote updated content to {file_path}")


async def fix_and_prune(
    changed_file: str,
    dataset_name: str = ingest.DEFAULT_DATASET,
    test_runner=fake_tests.check,
    groq_api_key: Optional[str] = None,
    top_k: int = 15,
) -> Tuple[str, List[dict]]:
    session_id = str(uuid.uuid4())
    print(f"[session {session_id}] investigating blast radius of {changed_file}")

    dependents = await find_dependents(changed_file, dataset_name, session_id=session_id, top_k=top_k)
    print(f"Candidate dependents found: {len(dependents)}")
    for f in dependents:
        print(f"  - {f}")

    broken, feedback = verify_dependents(dependents, test_runner=test_runner)
    print(f"Actually broken: {len(broken)} of {len(dependents)} candidate(s)")
    for f in broken:
        print(f"  - {f}")

    if broken:
        client = Groq(api_key=groq_api_key)
        for f in broken:
            print(f"Asking Groq to fix {f}...")
            fixed_content = ask_groq_to_fix(f, changed_file, client)
            apply_fix(f, fixed_content)

    # Prune the stale version of changed_file, using the manifest's
    # data_id from BEFORE this investigation's re-ingest below.
    manifest = ingest.load_manifest()
    prior = manifest.get(changed_file)
    if prior and prior.get("data_id"):
        old_data_id = prior["data_id"]
        print(f"Forgetting stale version of {changed_file} (data_id={old_data_id})...")
        await cognee.forget(data_id=uuid.UUID(old_data_id), dataset=dataset_name)
        print("Stale version pruned from memory.")
    else:
        print(f"[warn] no prior manifest entry for {changed_file} -- nothing to forget (first ingest?)")

    # Re-ingest: changed_file and any fixed dependents now have different
    # content than what's in the manifest, so ingest_repo()'s existing
    # content-hash comparison picks them up automatically -- everything
    # else is skipped, same as any normal incremental ingest.
    print("Re-ingesting changed/fixed files...")
    await ingest.ingest_repo(dataset_name=dataset_name)

    return session_id, feedback


if __name__ == "__main__":
    import argparse
    import os
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Blast-radius debugging demo")
    parser.add_argument("changed_file", help="Relative path, e.g. demo_repo/db.py")
    parser.add_argument("--dataset", default=ingest.DEFAULT_DATASET)
    parser.add_argument("--real-tests", action="store_true",
                         help="Use debug/real_tests.py instead of the scripted fake_tests.py default")
    parser.add_argument("--top-k", type=int, default=15,
                         help="How many candidate dependents to pull from recall() before verifying. "
                              "Cast a wide net here on purpose (repo is only 14 files) -- "
                              "verify_dependents() is what filters false positives out, not top_k.")
    args = parser.parse_args()

    runner = real_tests.check if args.real_tests else fake_tests.check

    session_id, feedback = asyncio.run(
        fix_and_prune(args.changed_file, dataset_name=args.dataset, test_runner=runner,
                      groq_api_key=os.getenv("GROQ_API_KEY"), top_k=args.top_k)
    )
    print(f"\nDone. session_id={session_id}")
    print(f"feedback: {feedback}")
