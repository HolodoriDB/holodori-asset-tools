from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from logging import getLogger
from pathlib import Path
from typing import Optional, Union

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = getLogger("catalog")

APPVER_URL = "https://raw.githubusercontent.com/HolodoriDB/holodori-app-protos/refs/heads/main/global/appver.json"
OCTO_API_KEY = "B46OtKlGGHoz6sxbOWDe3VUvBsagXxr5av38IQIKUKo="
OCTO_CLIENT_KEY = "CwFhQ+S5m4nERWVaq5oFZIP0cZLc0j7O/zllG0UYVNo="
OCTO_LIST_URL = (
    "https://us.game-hololive-dreams.com/asset/v2/pub/a/5/v/200001/list/{gen}"
)


@lru_cache(maxsize=1)
def appver(url: str = APPVER_URL) -> dict:
    try:
        return httpx.get(url, timeout=30).json()
    except Exception as e:
        logger.warning("appver fetch failed (%s); using bundled keys", e)
        return {
            "version_name": "",
            "android_octo_key": OCTO_API_KEY,
            "android_app_octo_key": OCTO_CLIENT_KEY,
        }


@dataclass
class Entry:
    name: str
    objectName: str
    url: str
    md5: str = ""
    size: int = 0
    dependencies: list[int] = field(default_factory=list)
    id: int = 0


@dataclass
class Catalog:
    revisionId: int = 0
    urlFormat: str = ""
    serverTime: int = 0
    assetBundles: list[Entry] = field(default_factory=list)
    resources: list[Entry] = field(default_factory=list)

    def save(self, path: Union[str, Path]) -> None:
        Path(path).write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Catalog":
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        pick = lambda e: Entry(
            e["name"],
            e["objectName"],
            e["url"],
            e.get("md5", ""),
            e.get("size", 0),
            e.get("dependencies", []),
            e.get("id", 0),
        )
        return cls(
            obj.get("revisionId", 0),
            obj.get("urlFormat", ""),
            obj.get("serverTime", 0),
            [pick(e) for e in obj.get("assetBundles", [])],
            [pick(e) for e in obj.get("resources", [])],
        )

    def _bundle_index(self) -> dict[str, int]:
        cache = getattr(self, "_bidx", None)
        if cache is None:
            cache = {e.name: i for i, e in enumerate(self.assetBundles)}
            self._bidx = cache
        return cache

    def _resource_index(self) -> dict[str, "Entry"]:
        cache = getattr(self, "_ridx", None)
        if cache is None:
            cache = {e.name: e for e in self.resources}
            self._ridx = cache
        return cache

    def _by_id(self) -> dict[int, "Entry"]:
        cache = getattr(self, "_idmap", None)
        if cache is None:
            cache = {e.id: e for e in self.assetBundles}
            cache.update({e.id: e for e in self.resources})
            self._idmap = cache
        return cache

    def required(self, name: str, group: str) -> list["Entry"]:
        if group == "assetbundles":
            idx = self._bundle_index()
            if name not in idx:
                return []
            start = self.assetBundles[idx[name]]
            byid = self._by_id()
            seen: set[int] = set()
            order: list["Entry"] = []
            stack = [start]
            while stack:
                e = stack.pop()
                if e.id in seen:
                    continue
                seen.add(e.id)
                order.append(e)
                for d in e.dependencies:
                    dep = byid.get(d)
                    if dep is not None and dep.id not in seen:
                        stack.append(dep)
            return [start] + sorted(
                (e for e in order if e is not start), key=lambda x: x.name
            )
        res = self._resource_index()
        entry = res.get(name)
        if entry is None:
            return []
        req = [entry]
        if name.endswith((".acb", ".awb")):
            stem = name.rsplit(".", 1)[0]
            sib = stem + (".awb" if name.endswith(".acb") else ".acb")
            if sib in res:
                req.append(res[sib])
        return req


def _uvarint(b: bytes, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        x = b[i]
        i += 1
        result |= (x & 0x7F) << shift
        if not x & 0x80:
            return result, i
        shift += 7


def _fields(buf: bytes) -> list[tuple[int, int, object]]:
    out: list[tuple[int, int, object]] = []
    i, n = 0, len(buf)
    while i < n:
        tag, i = _uvarint(buf, i)
        f, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = _uvarint(buf, i)
        elif wt == 1:
            v, i = buf[i : i + 8], i + 8
        elif wt == 2:
            ln, i = _uvarint(buf, i)
            v, i = buf[i : i + ln], i + ln
        elif wt == 5:
            v, i = buf[i : i + 4], i + 4
        else:
            raise ValueError(wt)
        out.append((f, wt, v))
    return out


def _packed(v: bytes) -> list[int]:
    out, i, n = [], 0, len(v)
    while i < n:
        x, i = _uvarint(v, i)
        out.append(x)
    return out


def _parse_entry(buf: bytes) -> dict:
    e: dict = {}
    for f, wt, v in _fields(buf):
        if f == 1:
            e["id"] = v
        elif f == 2:
            e["name"] = v.decode()
        elif f == 3:
            e["size"] = v
        elif f == 5:
            e["md5"] = v.decode()
        elif f == 6:
            e["dependencies"] = _packed(v)
        elif f == 7:
            e["objectName"] = v.decode()
    return e


def _parse_database(buf: bytes) -> dict:
    db: dict = {
        "revisionId": 0,
        "urlFormat": "",
        "serverTime": 0,
        "bundles": [],
        "resources": [],
    }
    for f, wt, v in _fields(buf):
        if f == 1:
            db["revisionId"] = v
        elif f == 2:
            db["bundles"].append(_parse_entry(v))
        elif f == 3:
            db["resources"].append(_parse_entry(v))
        elif f == 4:
            db["urlFormat"] = v.decode()
        elif f == 7:
            db["serverTime"] = v
    return db


def _decrypt_body(body: bytes, api_key: str) -> bytes:
    key = hashlib.sha256(api_key.encode()).digest()
    pt = Cipher(algorithms.AES(key), modes.CBC(body[:16])).decryptor().update(body[16:])
    pad = pt[-1]
    return pt[:-pad] if 1 <= pad <= 16 else pt


def fetch(gen: int = 0, url: Optional[str] = None) -> Catalog:
    info = appver()
    api_key = info.get("android_octo_key", OCTO_API_KEY)
    client_key = info.get("android_app_octo_key", OCTO_CLIENT_KEY)
    logger.info("app version %s", info.get("version_name") or "?")
    with httpx.Client(http2=True, timeout=120) as c:
        r = c.get(
            (url or OCTO_LIST_URL).format(gen=gen),
            headers={"X-OCTO-KEY": api_key, "X-APP-OCTO-KEY": client_key},
        )
    r.raise_for_status()
    db = _parse_database(_decrypt_body(r.content, api_key))
    fmt = db["urlFormat"]
    build = lambda lst: [
        Entry(
            e.get("name", ""),
            e.get("objectName", ""),
            fmt.replace("{o}", e.get("objectName", "")),
            e.get("md5", ""),
            e.get("size", 0),
            e.get("dependencies", []),
            e.get("id", 0),
        )
        for e in lst
    ]
    return Catalog(
        db["revisionId"],
        fmt,
        db["serverTime"],
        build(db["bundles"]),
        build(db["resources"]),
    )


def get(path: Optional[Union[str, Path]] = None, gen: int = 0) -> Catalog:
    if path and Path(path).exists():
        return Catalog.load(path)
    catalog = fetch(gen)
    if path:
        catalog.save(path)
    return catalog
