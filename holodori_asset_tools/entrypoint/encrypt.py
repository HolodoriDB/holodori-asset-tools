from __future__ import annotations

import argparse
from logging import getLogger
from pathlib import Path

from .. import crypto
from . import io_pairs

logger = getLogger("encrypt")


def main(args: argparse.Namespace) -> int:
    indir, outdir = Path(args.indir), Path(args.outdir)
    assert indir.resolve() != outdir.resolve(), "input and output must differ"
    for src, dest in io_pairs(indir, outdir):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(crypto.encrypt(src.read_bytes(), src.name, args.kind))
        logger.info("%s -> %s", src, dest)
    return 0
