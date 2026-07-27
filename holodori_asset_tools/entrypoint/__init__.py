from __future__ import annotations

from pathlib import Path
from typing import Iterator


def io_pairs(indir: Path, outdir: Path) -> Iterator[tuple[Path, Path]]:
    if indir.is_file():
        dest = outdir / indir.name if outdir.is_dir() or not outdir.suffix else outdir
        yield indir, dest
        return
    for src in sorted(indir.rglob("*")):
        if src.is_file():
            yield src, outdir / src.relative_to(indir)
