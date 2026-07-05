# CodeGraph Memory

Dependency-aware coding memory + blast-radius debugging, built on Cognee.

**Thesis:** most memory demos show an AI that never forgets. This one forgets
on purpose — recalling only what a task needs, and pruning what's gone
stale — because for a coding agent, remembering everything is exactly what
causes context rot and blows up cost.

Two connected capabilities, one graph:
- **Read path** — asked to build/test a module, pull only the files it
  actually depends on, not the whole repo.
- **Write path** — when a file changes, find which *other* files might
  break, verify with real tests (don't assume), fix only the real
  breakages, then prune the old broken version from memory.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in LLM_API_KEY and GROQ_API_KEY with your Groq key (same key, two places)
# on Windows, also fill in DATA_ROOT_DIRECTORY / SYSTEM_ROOT_DIRECTORY -- see
# the comment in .env.example, this avoids a real MAX_PATH failure mode
python memory/verify_setup.py
```

`verify_setup.py` should end with `ALL CHECKS PASSED` before you go any
further — it tests the LLM connection, embeddings, ingestion, and the
`data_id` lookup mechanism everything else depends on.

## Running the demo

```bash
python cli.py ingest       # ingest demo_repo,
python cli.py visualize    # write memory/graph.html
python cli.py build "write a test for JWT auth"
python cli.py fix demo_repo/db.py
```

`cli.py` is a thin wrapper around `orchestrator.py`, which composes
`memory/` (ingest + retrieve) and `debug/` (blast-radius) — see that file
for the two demo-able entry points, `build()` and `fix()`.

## What's real vs. what's scripted

- **Read path (`build`)** is fully real: live `recall()` against Cognee,
  real token counts, real file attribution.
- **Write path (`fix`)** finds dependents and fixes/forgets/re-ingests for
  real, but **test verification is scripted** (`debug/fake_tests.py`),
  because `demo_repo` has no real test suite. This isn't a shortcut hiding
  a gap — it's the build plan's own explicit fallback for this exact
  situation. `debug/real_tests.py` implements the same interface against
  real `pytest` and is a one-line swap (`--real-tests`) the moment test
  files exist under `demo_repo/<pkg>/tests/test_<name>.py`.

## Corrections made along the way (worth knowing if you extend this)

A few things in the original plan sketch didn't hold up against the actual
installed Cognee SDK (1.2.2) — noted here so nobody re-discovers them the
hard way:

1. **`remember()`'s return value has no usable `data_id`.** We ingest with
   an explicit `label=<relative_path>` per file instead, then resolve
   `data_id` afterward via `cognee.datasets.list_data()` and match on that
   label. This is what `memory/manifest.json` is built from.
2. **`recall()` needs explicit `query_type=SearchType.CHUNKS`.** Left
   unset, `auto_route` can classify a natural-language query as an
   LLM-completion type, whose response carries no file provenance at all.
3. **For `CHUNKS`, `only_context` must be `False`, not `True`.** `True`
   routes through a method that flattens results into one joined string
   by design (no metadata survives). `False` returns the raw per-chunk
   payload dicts, each stamped with `document_id` — that's the one with
   provenance.
4. **Files with identical content collide.** Cognee derives each data
   item's `id` from content, so e.g. multiple empty `__init__.py` files in
   the same ingest batch caused a real `UNIQUE constraint` failure. Fixed
   by giving every file distinct content.
5. **Windows-specific:** `ProactorEventLoop`'s SSL handling can hang
   against TLS-inspecting corporate proxies/antivirus (all our scripts
   force `WindowsSelectorEventLoopPolicy`), and Cognee's default storage
   path nested deep inside a venv can exceed `MAX_PATH` (fixed via
   `DATA_ROOT_DIRECTORY`/`SYSTEM_ROOT_DIRECTORY` in `.env`).
6. **No native `groq` provider in Cognee.** Wired as `LLM_PROVIDER=custom`
   with `LLM_ENDPOINT=https://api.groq.com/openai/v1` — Groq's API is
   OpenAI-compatible, which is exactly what `custom` is for. Embeddings
   use `fastembed` (local, free) since Groq doesn't serve embedding
   models.

## Measured impact (from an actual run, not projected)

**Read path** — query: `"write a test for JWT auth"`, against the 14-file `demo_repo`:

| | tokens | % of full repo |
|---|---|---|
| Full repo | 3,337 | 100% |
| Recalled | 791 | 23.7% |

Recalled from exactly 3 files, all genuinely relevant: `auth/__init__.py`,
`auth/dependencies.py`, `auth/jwt_auth.py`. `rag_service/retriever.py` —
the deliberately-isolated file — was correctly excluded.

**Write path** — changed `db.py` (renamed `Database.get()` →
`get_by_id()`, a real breaking change, confirmed via a smoke test that
throws a genuine `AttributeError` beforehand):

- 5 candidate dependents surfaced (wide net on purpose — verification is
  the actual safety net, not a tight `top_k`)
- 2 genuinely broken (`crud/projects.py`, `crud/tasks.py`), fixed via one
  Groq call each
- 3 candidates correctly left untouched, including `rag_service/retriever.py`
  — which surfaced as a *false positive* candidate (its own docstring
  mentions `db.py` by name, explaining why it's *not* dependent on it —
  enough textual overlap for recall to flag it, and exactly the kind of
  case verification exists to catch) and was correctly never modified
- Stale `db.py` version pruned via `forget()`; changed + fixed files
  re-ingested automatically via the existing content-hash comparison

## Known limitations / honest future work

- **`cognee.improve()`'s feedback loop doesn't bridge to this project's
  retrieval path.** `feedback_alpha` is a float weighting knob, not a
  place to submit our per-file ground truth, and the real feedback
  submission APIs (`add_feedback`, `add_frequency_weights`) are scoped to
  Cognee's conversational QA/session memory (keyed by `qa_id`), not the
  `add()`/`cognify()`/`recall(query_type=CHUNKS)` code-graph path used
  throughout this project. Closing that loop for real would mean routing
  dependent-finding through the QA/session subsystem instead — a
  reasonable next step, not something faked here.
- **Write-path verification is scripted** (see above) since `demo_repo`
  has no real test suite. `debug/real_tests.py` is the real-pytest
  swap-in, one flag away, the moment test files exist.
- **Dependent-finding is semantic, not a literal import-graph
  traversal** — it's asking `recall()` "what depends on X," which ranks
  by relevance to that question, not by walking actual `import`
  statements. This is why verification (not retrieval) is the real
  correctness guarantee in the write path.

## Repo structure

```
codegraph-memory/
├── demo_repo/            # sample FastAPI project Cognee ingests
├── memory/
│   ├── ingest.py         # ingest + build file_path -> data_id manifest
│   ├── retrieve.py       # scoped recall + token comparison
│   ├── manifest.json     # generated by ingest.py
│   └── verify_setup.py   # run this first
├── debug/
│   ├── blast_radius.py   # find dependents, verify, fix, forget, re-ingest
│   ├── fake_tests.py     # scripted verification (current default)
│   └── real_tests.py     # real pytest, same interface, swap-in ready
├── orchestrator.py        # composes memory + Groq + debug
├── cli.py                 # demo entrypoint
├── .env.example
└── requirements.txt
```
