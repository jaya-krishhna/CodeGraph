"""
memory/ingest.py — Step 2: ingest demo_repo into Cognee, and build a
durable file_path -> data_id manifest that debug/blast_radius.py will
rely on later for `forget()`-ing a stale file version.

Why a manifest instead of trusting remember()/add()'s return value:
remember() returns a RememberResult whose only stable fields are
`done`/`session_id` — no usable data_id. So instead we ingest with an
explicit `label` per file (the relative path), then look the file back
up via cognee.datasets.list_data() after cognify() finishes, matching
on that label. This round-trip was confirmed working end-to-end via
memory/verify_setup.py before this file was written.

Usage:
    python memory/ingest.py                  # ingest demo_repo, skip unchanged files
    python memory/ingest.py --force           # re-ingest everything
    python memory/ingest.py --visualize       # also write graph.html
"""

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv

# Must run before `import cognee`: cognee's storage-path settings load via
# pydantic, which reads .env on its own — but LOG_LEVEL and a few other
# settings are read with plain os.getenv(), which only sees real OS env
# vars. Loading .env here ensures both paths see the same values.
load_dotenv()

# Windows fix: see memory/verify_setup.py for why this is needed —
# ProactorEventLoop's SSL handling can hang against TLS-inspecting
# corporate proxies/antivirus. Harmless no-op on Linux/macOS.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import cognee
from cognee.tasks.ingestion.data_item import DataItem

MANIFEST_PATH = Path(__file__).parent / "manifest.json"
DEFAULT_DATASET = "fastapi_demo"
DEFAULT_REPO_PATH = Path(__file__).parent.parent / "demo_repo"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_manifest() -> Dict[str, dict]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: Dict[str, dict]) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def discover_py_files(repo_path: Path) -> List[Path]:
    return sorted(p for p in repo_path.rglob("*.py"))


def _rel_path(path: Path, repo_path: Path) -> str:
    # Relative to the repo's parent, so labels look like "demo_repo/auth/models.py"
    # rather than an absolute path — stable across machines, readable in the manifest.
    return str(path.relative_to(repo_path.parent)).replace("\\", "/")


async def ingest_repo(
    repo_path: str = None,
    dataset_name: str = DEFAULT_DATASET,
    force: bool = False,
) -> Dict[str, dict]:
    repo_path_p = Path(repo_path) if repo_path else DEFAULT_REPO_PATH
    manifest = load_manifest()

    files = discover_py_files(repo_path_p)
    if not files:
        print(f"No .py files found under {repo_path_p}")
        return manifest

    to_ingest: List[Tuple[str, str, str]] = []  # (rel_path, content, content_hash)
    unchanged: List[str] = []

    for path in files:
        rel = _rel_path(path, repo_path_p)
        content = path.read_text(encoding="utf-8")
        content_hash = _hash(content)
        prior = manifest.get(rel)
        if not force and prior and prior.get("content_hash") == content_hash:
            unchanged.append(rel)
            continue
        to_ingest.append((rel, content, content_hash))

    if unchanged:
        print(f"Skipping {len(unchanged)} unchanged file(s) (use --force to re-ingest anyway)")

    if not to_ingest:
        print("Nothing new to ingest.")
        return manifest

    # label=rel_path is the identifier we use to match each ingested item
    # back to its source file afterward — see module docstring.
    data_items = [DataItem(data=content, label=rel) for rel, content, _ in to_ingest]

    print(f"Ingesting {len(data_items)} file(s) into dataset '{dataset_name}'...")
    await cognee.add(data_items, dataset_name=dataset_name)
    print("add() complete, running cognify()...")
    await cognee.cognify(datasets=[dataset_name])
    print("cognify() complete.")

    all_datasets = await cognee.datasets.list_datasets()
    match = [d for d in all_datasets if getattr(d, "name", None) == dataset_name]
    if not match:
        raise RuntimeError(f"Could not find dataset '{dataset_name}' after ingest — this shouldn't happen.")
    dataset_id = match[0].id

    data_records = await cognee.datasets.list_data(dataset_id)
    by_label = {getattr(d, "label", None): d for d in data_records}

    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for rel, _content, content_hash in to_ingest:
        record = by_label.get(rel)
        if record is None:
            print(f"[warn] no data record found for '{rel}' after ingest — manifest not updated for this file")
            continue
        manifest[rel] = {
            "data_id": str(record.id),
            "dataset_id": str(dataset_id),
            "dataset_name": dataset_name,
            "content_hash": content_hash,
            "last_ingested_at": now,
        }
        updated += 1

    save_manifest(manifest)
    print(f"Manifest updated ({updated} file(s)): {MANIFEST_PATH}")
    return manifest


async def visualize(dataset_name: str = DEFAULT_DATASET, out_path: str = None) -> str:
    out_path = out_path or str(Path(__file__).parent / "graph.html")
    path = await cognee.visualize_graph(destination_file_path=out_path, dataset=dataset_name)
    print(f"Graph visualization written to: {path}")
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest demo_repo into Cognee")
    parser.add_argument("--repo", default=None, help="Path to repo root (default: ../demo_repo)")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--force", action="store_true", help="Re-ingest even unchanged files")
    parser.add_argument("--visualize", action="store_true", help="Also write a graph visualization HTML file")
    args = parser.parse_args()

    async def _main():
        await ingest_repo(repo_path=args.repo, dataset_name=args.dataset, force=args.force)
        if args.visualize:
            await visualize(dataset_name=args.dataset)

    asyncio.run(_main())
