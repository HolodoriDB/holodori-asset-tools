from typing import Literal, Optional

from . import bundle, resource
from .mask import mask

__all__ = ["bundle", "resource", "mask", "decrypt", "encrypt"]


def decrypt(data: bytes, name: str) -> bytes:
    if data[: len(resource.MAGIC)] == resource.MAGIC:
        return resource.decrypt(data, name)
    return bundle.decrypt(data, name)


def encrypt(
    data: bytes, name: str, kind: Optional[Literal["bundle", "resource"]] = None
) -> bytes:
    if kind == "resource":
        return resource.encrypt(data, name)
    if kind == "bundle":
        return bundle.encrypt(data, name)
    if data[: len(bundle.UNITY_SIGNATURE)] == bundle.UNITY_SIGNATURE:
        return bundle.encrypt(data, name)
    return resource.encrypt(data, name)
