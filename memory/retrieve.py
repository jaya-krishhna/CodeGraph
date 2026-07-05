"""
memory/retrieve.py — Step 3: read path — scoped retrieval + token
comparison, using cognee.recall().

Key correction vs. the original plan sketch: recall() defaults to a
full QA pipeline (auto_route, a system prompt, an actual generated
answer) and returns a discriminated union of 5 possible entry types —
`"\n".join(str(r) for r in recalled)` would silently stringify Pydantic
response objects instead of giving clean recalled text, which would
quietly produce a wrong (probably much larger, and wrong-shaped) number
for the token-comparison demo instead of an error. We pass
only_context=True to steer recall() toward raw context entries, and
still defensively handle every entry type it can return (verified
against the installed SDK), so nothing gets silently mis-measured if
only_context doesn't fully suppress the others.

Each recalled item's metadata["data_id"] is the ingested Data item's id
(confirmed against cognee's own normalize_search_payload.py docstring:
"document_id is the ingested Data item's id ... exposed here as
data_id"). That's exactly what memory/manifest.json is keyed on, so we
invert the manifest to report which source *files* a recall actually
pulled in — not just an opaque blob of recalled text.

Second correction, found by actually running this against real data:
leaving query_type unset lets auto_route classify natural-language
queries (like "write a test for JWT auth") as an LLM-completion type
(e.g. GRAPH_COMPLETION), whose raw payload is a synthesized answer, not
a chunk hit — so no document_id is ever present and file-mapping
silently fails even though token counting still "works" (it's counting
tokens in an LLM answer, not recalled source). Passing
query_type=SearchType.CHUNKS explicitly forces the raw-chunk retrieval
path that actually carries per-chunk document_id provenance. Traced
through recall.py to confirm an explicit query_type overrides
auto_route rather than being ignored by it.

Third correction, found by inspecting ChunksRetriever directly after the
above still failed to map files: only_context=True routes CHUNKS through
get_context_from_objects, which flattens chunks into one joined string
by design (no metadata survives that path at all). only_context=False
routes through get_completion_from_context, which for CHUNKS specifically
just returns the raw chunk payload dicts -- each one stamped with
document_id at chunking time (confirmed in TextChunker.py). That's the
combination (query_type=CHUNKS, only_context=False) that actually
carries provenance through to entry.metadata["data_id"].

Usage:
    python memory/retrieve.py "write a test for JWT auth"
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Tuple

# Windows fix: see memory/verify_setup.py.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import cognee
import tiktoken
from cognee import SearchType

from ingest import DEFAULT_DATASET, DEFAULT_REPO_PATH, discover_py_files, load_manifest

enc = tiktoken.get_encoding("cl100k_base")


def _extract_text_and_data_id(entry) -> Tuple[str, Optional[str]]:
    """Pull clean text (+ a data_id, if present) out of one recall()
    entry, regardless of which of the 5 possible response types it is."""
    source = getattr(entry, "source", None)

    if source in ("graph_context", "session_context"):
        return entry.content, None

    if source == "graph":
        data_id = entry.metadata.get("data_id") if entry.metadata else None
        if data_id is None:
            # Don't just report failure -- show exactly what's actually in
            # the entry so the real key names are visible instead of
            # guessed at again.
            print(f"[debug] no data_id in metadata for this entry. metadata={entry.metadata!r}")
            raw = getattr(entry, "raw", None)
            if raw:
                print(f"[debug] raw payload keys: {list(raw.keys())}")
                print(f"[debug] raw payload: {raw!r}"[:800])
        return entry.text, data_id

    if source in ("session", "trace"):
        # QA/agent-trace entries -- not raw source content. Shouldn't show
        # up with only_context=True, but if they do, surface it loudly
        # rather than silently folding it into the token count as if it
        # were recalled file content.
        print(f"[warn] unexpected recall() entry with source={source!r} -- only_context=True may not have fully suppressed QA/trace entries")
        return f"[{source} entry, not raw context: {entry}]", None

    print(f"[warn] unrecognized recall() entry type: {type(entry)} -- treating as opaque text")
    return str(entry), None


def full_repo_text(repo_path: Path = None) -> str:
    """Concatenate every .py file in the repo, for the 'full repo' side
    of the token comparison."""
    repo_path = repo_path or DEFAULT_REPO_PATH
    parts = [f.read_text(encoding="utf-8") for f in discover_py_files(repo_path)]
    return "\n".join(parts)


def _manifest_lookup_by_data_id(manifest: dict) -> dict:
    return {v["data_id"]: file_path for file_path, v in manifest.items()}


async def scoped_context(
    query: str,
    dataset_name: str = DEFAULT_DATASET,
    top_k: int = 3,
) -> dict:
    # only_context=True is deliberately NOT used here: for query_type=CHUNKS,
    # Cognee's ChunksRetriever branches on this flag between two completely
    # different return shapes. only_context=True calls get_context_from_objects,
    # which does "\n".join(chunk["text"] for chunk in chunks) -- a flattened
    # string, no metadata, by design. only_context=False calls
    # get_completion_from_context, which (for CHUNKS specifically, per its own
    # docstring: "we do not generate a completion, we just return the payloads
    # of found chunks") returns the raw chunk payload dicts, each stamped with
    # document_id at chunking time (confirmed in TextChunker.py). That's the
    # one that actually gives us provenance.
    recalled = await cognee.recall(
        query_text=query,
        datasets=[dataset_name],
        query_type=SearchType.CHUNKS,
        only_context=False,
        top_k=top_k,
    )

    manifest = load_manifest()
    by_data_id = _manifest_lookup_by_data_id(manifest)

    texts = []
    recalled_files = []
    for entry in recalled:
        text, data_id = _extract_text_and_data_id(entry)
        texts.append(text)
        if data_id and data_id in by_data_id:
            recalled_files.append(by_data_id[data_id])

    recalled_text = "\n".join(texts)
    recalled_files = sorted(set(recalled_files))

    full_text = full_repo_text()
    full_tokens = len(enc.encode(full_text))
    recalled_tokens = len(enc.encode(recalled_text))
    pct = f"{recalled_tokens / full_tokens:.1%}" if full_tokens else "n/a"

    print(f"Query: {query!r}")
    print(f"Full repo tokens: {full_tokens}")
    print(f"Recalled tokens:  {recalled_tokens}  ({pct} of full repo)")
    if recalled_files:
        print(f"Recalled from {len(recalled_files)} file(s):")
        for f in recalled_files:
            print(f"  - {f}")
    else:
        print("(Could not map any recalled entries back to a source file via the manifest — "
              "check that memory/ingest.py has been run for this dataset)")

    return {
        "query": query,
        "recalled_text": recalled_text,
        "recalled_files": recalled_files,
        "full_tokens": full_tokens,
        "recalled_tokens": recalled_tokens,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scoped retrieval + token comparison demo")
    parser.add_argument("query", help="What to recall, e.g. 'write a test for JWT auth'")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=3,
                         help="Cognee's own default (15) returns nearly the whole "
                              "14-file demo_repo since chunks-per-file is low here — "
                              "3 is tuned for this repo's size, not a general default.")
    args = parser.parse_args()

    asyncio.run(scoped_context(args.query, dataset_name=args.dataset, top_k=args.top_k))
