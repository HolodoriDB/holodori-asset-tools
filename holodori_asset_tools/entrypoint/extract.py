from __future__ import annotations

import argparse
import json
from logging import getLogger
from pathlib import Path
from typing import Union

import cricodecs

from .. import crypto

logger = getLogger("extract")

UNITY_VERSION = "6000.3.15f1"

_KEEP = ("Sprite", "Texture2D", "TextAsset", "MonoBehaviour", "AnimationClip")


def _unitypy():
    import warnings

    import UnityPy
    from UnityPy.exceptions import UnityVersionFallbackWarning

    UnityPy.config.FALLBACK_UNITY_VERSION = UNITY_VERSION
    warnings.simplefilter("ignore", UnityVersionFallbackWarning)
    return UnityPy


class AssetBundle:
    def __init__(self, path: Union[str, Path], name: str) -> None:
        self.path = Path(path)
        self.name = name

    def load(self):
        return _unitypy().load(crypto.decrypt(self.path.read_bytes(), self.name))

    def extract(self, outdir: Union[str, Path]) -> set[Path]:
        env = self.load()
        out = Path(outdir) / self.name
        objects = [o for o in env.objects if o.type.name in _KEEP]
        data = {o.path_id: o.read() for o in objects}
        sprites = {
            d.m_Name for o, d in zip(objects, data.values()) if o.type.name == "Sprite"
        }
        created: set[Path] = set()
        for obj in objects:
            d = data[obj.path_id]
            if obj.type.name == "Texture2D" and d.m_Name in sprites:
                continue
            dest = out / (d.m_Name or str(obj.path_id))
            dest.parent.mkdir(parents=True, exist_ok=True)
            if obj.type.name in ("Sprite", "Texture2D"):
                dest = dest.with_suffix(".png")
                d.image.save(dest)
            elif obj.type.name == "TextAsset":
                script = d.m_Script
                dest.write_bytes(
                    script.encode("utf-8", "surrogateescape")
                    if isinstance(script, str)
                    else bytes(script)
                )
            else:
                dest = dest.with_suffix(".json")
                dest.write_text(
                    json.dumps(obj.read_typetree(), ensure_ascii=False),
                    encoding="utf-8",
                )
            created.add(dest)
        return created


def _wav(name: str, data: bytes) -> bytes:
    if name.endswith(".adx"):
        adx = cricodecs.adx.load_bytes(data)
        pcm = adx.decode()
        if pcm[:4] == b"RIFF":
            return pcm
        h = adx.header
        return cricodecs.wav.build_bytes(pcm, h.sample_rate, h.channels)
    return cricodecs.hca.decode(data)


def _extract_acb(src: Path, outdir: Path) -> set[Path]:
    acb = cricodecs.acb.load(str(src))
    count = acb.waveform_count
    created: set[Path] = set()
    for i in range(count):
        wav = _wav(acb.waveform_filename(i), acb.waveform_bytes(i))
        if count == 1:
            dest = outdir / (src.stem + ".wav")
        else:
            dest = outdir / src.stem / (Path(acb.waveform_filename(i)).stem + ".wav")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(wav)
        created.add(dest)
    return created


def _extract_usm(src: Path, outdir: Path) -> set[Path]:
    usm = cricodecs.usm.load(str(src))
    out = outdir / src.stem
    out.mkdir(parents=True, exist_ok=True)
    usm.extract(str(out))
    created: set[Path] = set()
    for f in sorted(out.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() in (".hca", ".adx"):
            wav = f.with_suffix(".wav")
            wav.write_bytes(_wav(f.name, f.read_bytes()))
            f.unlink()
            created.add(wav)
        else:
            created.add(f)
    return created


def _copy(src: Path, outdir: Path) -> set[Path]:
    dest = outdir / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())
    return {dest}


def _extract_one(src: Path, outdir: Path) -> set[Path]:
    ext = src.suffix.lower()
    if ext == ".acb":
        return _extract_acb(src, outdir)
    if ext == ".usm":
        return _extract_usm(src, outdir)
    if ext == ".awb":
        return set() if src.with_suffix(".acb").exists() else _copy(src, outdir)
    with open(src, "rb") as fp:
        head = fp.read(7)
    if ext == "" or head == b"UnityFS":
        return AssetBundle(src, src.name).extract(outdir)
    return _copy(src, outdir)


def main(args: argparse.Namespace) -> int:
    indir, outdir = Path(args.indir), Path(args.outdir)
    files = (
        [indir]
        if indir.is_file()
        else sorted(p for p in indir.rglob("*") if p.is_file())
    )
    for src in files:
        try:
            created = _extract_one(src, outdir)
            logger.info("%s -> %d files", src.name, len(created))
        except Exception as e:
            logger.error("%s failed: %s", src.name, e)
    return 0
