from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging import getLogger
from pathlib import Path

import httpx
from tqdm import tqdm

from .. import catalog, crypto
from ..catalog import Entry

logger = getLogger("download")


def main(args: argparse.Namespace) -> int:
    cat = catalog.get(args.catalog, args.gen)
    logger.info(
        "revision %d: %d bundles, %d resources",
        cat.revisionId,
        len(cat.assetBundles),
        len(cat.resources),
    )

    outdir = Path(args.outdir)
    pattern = re.compile(args.filter) if args.filter else None
    jobs: list[tuple[Path, Entry]] = []
    for kind, entries in (
        ("assetbundles", cat.assetBundles),
        ("resources", cat.resources),
    ):
        for entry in entries:
            if pattern and not pattern.search(entry.name):
                continue
            dest = outdir / kind / entry.name
            if args.no_overwrite and dest.exists():
                continue
            jobs.append((dest, entry))

    logger.info("downloading %d files to %s", len(jobs), outdir)
    client = httpx.Client(http2=True, timeout=120, follow_redirects=True)

    def download(job: tuple[Path, Entry]) -> None:
        dest, entry = job
        last: Exception | None = None
        for _ in range(3):
            try:
                r = client.get(entry.url)
                r.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(crypto.decrypt(r.content, entry.name))
                return
            except Exception as e:
                last = e
        logger.error("failed %s: %s", entry.name, last)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(download, job) for job in jobs]
        try:
            for future in tqdm(as_completed(futures), total=len(futures), unit="file"):
                future.result()
        except KeyboardInterrupt:
            pool.shutdown(wait=False, cancel_futures=True)
            return 1
    return 0
