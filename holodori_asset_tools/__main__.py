from __future__ import annotations

import argparse
import logging

from . import __version__


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

    parser = argparse.ArgumentParser(prog="holodori")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "decrypt", help="decrypt a directory of assets (files named by asset name)"
    )
    p.add_argument("indir")
    p.add_argument("outdir")

    p = sub.add_parser(
        "encrypt", help="encrypt a directory of assets (files named by asset name)"
    )
    p.add_argument("indir")
    p.add_argument("outdir")
    p.add_argument("--kind", choices=["bundle", "resource"], default=None)

    p = sub.add_parser(
        "download", help="download and decrypt assets into assetbundles/ and resources/"
    )
    p.add_argument("outdir")
    p.add_argument("--catalog", default="octo_list.json")
    p.add_argument("--gen", type=int, default=0)
    p.add_argument("--filter", default=None, help="regex on asset name")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--no-overwrite", action="store_true")

    p = sub.add_parser("serve", help="browse and download assets over HTTP")
    p.add_argument("--catalog", default="octo_list.json")
    p.add_argument("--gen", type=int, default=0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)

    p = sub.add_parser("extract", help="extract decrypted assetbundles with UnityPy")
    p.add_argument("indir")
    p.add_argument("outdir")

    args = parser.parse_args()
    if args.command == "decrypt":
        from .entrypoint.decrypt import main as run
    elif args.command == "encrypt":
        from .entrypoint.encrypt import main as run
    elif args.command == "download":
        from .entrypoint.download import main as run
    elif args.command == "extract":
        from .entrypoint.extract import main as run
    else:
        from .entrypoint.serve import main as run
    return run(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
