from __future__ import annotations

import argparse
import html
import io
import shutil
import tempfile
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging import getLogger
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

import httpx

from .. import catalog, crypto
from ..catalog import Catalog, Entry
from .extract import _extract_one

logger = getLogger("serve")

_index: dict[str, dict[str, Entry]] = {}
_client: httpx.Client
_catalog: Catalog

_EXTRACTABLE_RES = (".acb", ".awb", ".usm")

_STYLE = "body{font-family:monospace;background:#000;color:#ddd;margin:1rem}a{color:#8cf;text-decoration:none}a:hover{text-decoration:underline}i{color:#888}"


def _filesize(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{size} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _extractable(folder: str, name: str) -> bool:
    return folder == "assetbundles" or name.endswith(_EXTRACTABLE_RES)


def _row(folder: str, name: str, entry: Entry) -> tuple[str, str, str]:
    extra = f"<i>({_filesize(entry.size)})</i>"
    if _extractable(folder, name):
        extra += f' <a href="{quote(name)}?extract=1">extracted.zip</a>'
    return (name, quote(name), extra)


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


def _build_zip(folder: str, name: str) -> bytes:
    req = _catalog.required(name, folder)
    tmp = Path(tempfile.mkdtemp())
    try:
        staged, out = tmp / "staged", tmp / "out"
        staged.mkdir()
        out.mkdir()
        for e in req:
            dst = staged / e.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(crypto.decrypt(_client.get(e.url).content, e.name))
        for e in req:
            try:
                _extract_one(staged / e.name, out)
            except Exception as ex:
                logger.error("extract %s: %s", e.name, ex)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(out.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(out))
        return buf.getvalue()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        u = urlsplit(self.path)
        parts = [p for p in unquote(u.path).split("/") if p]
        want_extract = "extract" in parse_qs(u.query, keep_blank_values=True)
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
            rows = [_row(parts[0], n, e) for n, e in sorted(_index[parts[0]].items())]
            self._send_html(_page(parts[0], rows))
        elif len(parts) == 2 and parts[0] in _index and parts[1] in _index[parts[0]]:
            if want_extract and _extractable(parts[0], parts[1]):
                self._send_zip(parts[0], parts[1])
            else:
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

    def _send_zip(self, folder: str, name: str) -> None:
        try:
            data = _build_zip(folder, name)
        except Exception as e:
            self.send_error(502, str(e))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header(
            "Content-Disposition", f'attachment; filename="extracted_{name}.zip"'
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


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
