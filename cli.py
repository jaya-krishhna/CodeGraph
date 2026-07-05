"""
cli.py — Step 6: demo entrypoint.

Usage:
    python cli.py ingest                              # (re)ingest demo_repo
    python cli.py ingest --force                      # re-ingest everything, even unchanged
    python cli.py visualize                           # write memory/graph.html
    python cli.py build "write a test for JWT auth"   # read path
    python cli.py fix demo_repo/db.py                 # write path (scripted verification)
    python cli.py fix demo_repo/db.py --real-tests    # write path (real pytest, once tests exist)
"""

import asyncio
import sys
from pathlib import Path

# Windows fix: see memory/verify_setup.py for why.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent / "debug"))

from dotenv import load_dotenv
load_dotenv()

import orchestrator
import ingest


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CodeGraph Memory — demo CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Ingest demo_repo into Cognee")
    ingest_p.add_argument("--force", action="store_true", help="Re-ingest even unchanged files")

    sub.add_parser("visualize", help="Write a graph visualization HTML file")

    build_p = sub.add_parser("build", help="Read path: scoped retrieval + code generation")
    build_p.add_argument("query", help="e.g. 'write a test for JWT auth'")
    build_p.add_argument("--top-k", type=int, default=3)

    fix_p = sub.add_parser("fix", help="Write path: blast-radius fix + prune")
    fix_p.add_argument("changed_file", help="e.g. demo_repo/db.py")
    fix_p.add_argument("--real-tests", action="store_true",
                        help="Use real pytest (debug/real_tests.py) instead of the scripted default")
    fix_p.add_argument("--top-k", type=int, default=15)

    args = parser.parse_args()

    if args.command == "ingest":
        asyncio.run(ingest.ingest_repo(force=args.force))
    elif args.command == "visualize":
        asyncio.run(ingest.visualize())
    elif args.command == "build":
        asyncio.run(orchestrator.build(args.query, top_k=args.top_k))
    elif args.command == "fix":
        asyncio.run(orchestrator.fix(args.changed_file, use_real_tests=args.real_tests, top_k=args.top_k))


if __name__ == "__main__":
    main()
