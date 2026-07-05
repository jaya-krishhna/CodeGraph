"""
orchestrator.py — Step 5.

Composes the already-validated pieces in memory/ and debug/ into the two
demo-able flows. This file is intentionally short: its value is
composing, not containing new logic. cli.py is the thin argument-parsing
wrapper around these two functions.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent / "debug"))

import ingest
import retrieve
import blast_radius
import fake_tests
import real_tests
from groq import Groq

GROQ_MODEL = "llama-3.3-70b-versatile"


async def build(query: str, dataset_name: str = ingest.DEFAULT_DATASET, top_k: int = 3) -> str:
    """Read path: scoped retrieval (prints the token comparison + recalled
    file list) then one Groq call to actually generate code from that
    recalled context."""
    result = await retrieve.scoped_context(query, dataset_name=dataset_name, top_k=top_k)

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = f"""Here is recalled code context from the repository:

{result['recalled_text']}

Task: {query}

Return only the code, no explanation, no markdown fences."""
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    generated = response.choices[0].message.content.strip()

    print("\n--- Generated ---\n")
    print(generated)
    return generated


async def fix(
    changed_file: str,
    dataset_name: str = ingest.DEFAULT_DATASET,
    use_real_tests: bool = False,
    top_k: int = 15,
) -> tuple:
    """Write path: find dependents, verify, fix only real breakages,
    forget the stale version, re-ingest. See debug/blast_radius.py for
    the actual mechanism."""
    runner = real_tests.check if use_real_tests else fake_tests.check
    session_id, feedback = await blast_radius.fix_and_prune(
        changed_file,
        dataset_name=dataset_name,
        test_runner=runner,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        top_k=top_k,
    )
    return session_id, feedback
