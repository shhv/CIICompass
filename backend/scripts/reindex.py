"""CLI: full (or incremental) reindex of docs.oort.io into Chroma."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingest.pipeline import run_full_pipeline  # noqa: E402


async def _main(force: bool) -> None:
    result = await run_full_pipeline(force=force)
    print(result)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-embed all pages, ignoring content hashes")
    args = parser.parse_args()
    asyncio.run(_main(args.force))


if __name__ == "__main__":
    main()
