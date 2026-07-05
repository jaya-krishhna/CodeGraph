"""
memory/verify_setup.py — run this ONCE, right after you drop a real
GROQ_API_KEY into .env, before building anything else on top of Cognee.

It checks, in order:
  1. .env loads and the required vars are present
  2. Cognee's internal LLM connection works (the Groq-via-custom-endpoint
     wiring in .env.example is the untested part — this is where it gets
     tested)
  3. fastembed embeddings work (should need no key at all)
  4. add() + cognify() succeeds on one tiny snippet
  5. cognee.datasets.list_data() can resolve that snippet back to a
     data_id — this is the mechanism ingest.py will lean on for the
     file_path -> data_id manifest, so we confirm it here before
     depending on it elsewhere.
  6. cleans up the test dataset so it doesn't pollute the real one

Run: python memory/verify_setup.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Windows fix: the default ProactorEventLoop's SSL handling frequently hangs
# against corporate/antivirus TLS-inspecting proxies (same root cause as the
# CRYPT_E_NO_REVOCATION_CHECK curl error), even though sync requests work
# fine. SelectorEventLoop doesn't hit this. Harmless no-op on Linux/macOS.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DATASET = "verify_setup_smoke_test"


def check_env() -> None:
    load_dotenv()
    required = ["LLM_PROVIDER", "LLM_ENDPOINT", "LLM_MODEL", "LLM_API_KEY", "EMBEDDING_PROVIDER"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[FAIL] Missing required .env vars: {missing}")
        print("       Copy .env.example to .env and fill in LLM_API_KEY (your Groq key) first.")
        sys.exit(1)
    if os.getenv("LLM_API_KEY", "").startswith("your-"):
        print("[FAIL] LLM_API_KEY still looks like the placeholder from .env.example.")
        sys.exit(1)
    print("[ok] .env loaded, required vars present")


async def check_ingest_and_manifest_lookup() -> None:
    import cognee

    print("[..] add() + cognify() on one small snippet (this is the real LLM/embedding test)")
    snippet = "def add(a, b):\n    return a + b\n"
    await cognee.add(snippet, dataset_name=TEST_DATASET)
    await cognee.cognify(datasets=[TEST_DATASET])
    print("[ok] add() + cognify() succeeded — LLM and embedding connections both work")

    print("[..] resolving dataset_name -> dataset_id -> data_id (the manifest mechanism)")
    all_datasets = await cognee.datasets.list_datasets()
    match = [d for d in all_datasets if getattr(d, "name", None) == TEST_DATASET]
    if not match:
        print(f"[FAIL] Could not find dataset '{TEST_DATASET}' via list_datasets(). Got: {all_datasets}")
        sys.exit(1)
    dataset_id = match[0].id
    print(f"[ok] resolved dataset_id: {dataset_id}")

    data_items = await cognee.datasets.list_data(dataset_id)
    if not data_items:
        print("[FAIL] list_data() returned nothing for the freshly-ingested dataset.")
        sys.exit(1)
    print(f"[ok] list_data() returned {len(data_items)} item(s):")
    for item in data_items:
        print(f"     - id={getattr(item, 'id', '?')} name={getattr(item, 'name', '?')}")
    print("[ok] this confirms ingest.py can build a file_path -> data_id manifest this way")


async def check_recall() -> None:
    import cognee

    print("[..] recall() against the freshly-ingested snippet")
    results = await cognee.recall(query_text="a function that adds two numbers", datasets=[TEST_DATASET])
    print(f"[ok] recall() returned {len(results)} result(s)")


async def cleanup() -> None:
    import cognee

    print("[..] cleaning up test dataset")
    all_datasets = await cognee.datasets.list_datasets()
    match = [d for d in all_datasets if getattr(d, "name", None) == TEST_DATASET]
    if match:
        # empty_dataset() removes all data in the dataset without needing
        # per-item data_ids (delete_data() needs dataset_id + data_id together
        # and there's no delete_dataset() — empty_dataset is the right scoped
        # call here, confirmed against the installed SDK).
        await cognee.datasets.empty_dataset(match[0].id)
    print("[ok] cleanup done")


async def main() -> None:
    check_env()
    await check_ingest_and_manifest_lookup()
    await check_recall()
    await cleanup()
    print("\nALL CHECKS PASSED — safe to build memory/ingest.py on top of this.")


if __name__ == "__main__":
    asyncio.run(main())
