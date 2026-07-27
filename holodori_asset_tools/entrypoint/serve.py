from __future__ import annotations

import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging import getLogger
from urllib.parse import quote, unquote

import httpx

from .. import catalog, crypto
from ..catalog import Catalog, Entry

logger = getLogger("serve")

_index: dict[str, dict[str, Entry]] = {}
_client: httpx.Client
_catalog: Catalog

_STYLE = "body{font-family:monospace;background:#000;color:#ddd;margin:1rem}a{color:#8cf;text-decoration:none}a:hover{text-decoration:underline}i{color:#888}"


def _filesize(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{size} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _page(title: str, rows: list[tuple[str, str, str]]) -> bytes:
    out = [
        f"<!DOCTYPE html><html><head><meta charset=utf-8><style>{_STYLE}</style>",
        f"<title>{html.escape(title)}</title></head><body>",
        f"<h2>{html.escape(title)}</h2><i>{len(rows)} items</i><hr><ul>",
        '<li><a href="..">..</a></li>',
    ]
    for name, href, extra in rows:
        out.append(f'<li><a href="{href}">{html.escape(name)}</a> {extra}</li>')
    out.append("</ul></body></html>")
    return "".join(out).encode("utf-8", "surrogateescape")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        parts = [p for p in unquote(self.path).split("/") if p]
        if not parts:
            self._send_html(
                _page(
                    "holodori assets",
                    [
                        (f"{k}/", f"{quote(k)}/", f"<i>({len(v)})</i>")
                        for k, v in _index.items()
                    ],
                )
            )
        elif len(parts) == 1 and parts[0] in _index:
            rows = [
                (n, quote(n), f"<i>({_filesize(e.size)})</i>")
                for n, e in sorted(_index[parts[0]].items())
            ]
            self._send_html(_page(parts[0], rows))
        elif len(parts) == 2 and parts[0] in _index and parts[1] in _index[parts[0]]:
            self._send_file(_index[parts[0]][parts[1]])
        else:
            self.send_error(404)

    def _send_html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, entry: Entry) -> None:
        try:
            body = crypto.decrypt(_client.get(entry.url).content, entry.name)
        except Exception as e:
            self.send_error(502, str(e))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{entry.name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(args: argparse.Namespace) -> int:
    global _index, _client, _catalog
    _catalog = catalog.get(args.catalog, args.gen)
    _index = {
        "assetbundles": {e.name: e for e in _catalog.assetBundles},
        "resources": {e.name: e for e in _catalog.resources},
    }
    _client = httpx.Client(http2=True, timeout=120, follow_redirects=True)
    logger.info(
        "revision %d: %d bundles, %d resources",
        _catalog.revisionId,
        len(_catalog.assetBundles),
        len(_catalog.resources),
    )
    logger.info("serving on http://%s:%d/", args.host, args.port)
    try:
        ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0
