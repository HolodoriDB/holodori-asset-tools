from __future__ import annotations

import argparse
from logging import getLogger
from pathlib import Path

from .. import crypto

logger = getLogger("encrypt")


def main(args: argparse.Namespace) -> int:
    indir, outdir = Path(args.indir), Path(args.outdir)
    assert (
        indir.resolve() != outdir.resolve()
    ), "input and output directories must differ"
    for src in sorted(indir.rglob("*")):
        if not src.is_file():
            continue
        dest = outdir / src.relative_to(indir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(crypto.encrypt(src.read_bytes(), src.name, args.kind))
        logger.info("%s -> %s", src, dest)
    return 0
