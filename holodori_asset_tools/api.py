from __future__ import annotations

import gzip
import hashlib
import struct
from datetime import datetime

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

__all__ = [
    "API_SECRET",
    "encrypt",
    "decrypt",
    "encrypt_request",
    "decrypt_response",
    "frame",
    "unframe",
    "decode_response",
    "dotnet_ticks",
    "app_request_id",
]

API_SECRET = b"BJYZ0w3DJm"
_KEY = hashlib.md5(API_SECRET).digest()

_DOTNET_EPOCH = datetime(1, 1, 1)


def dotnet_ticks() -> int:
    # .NET DateTime.Now ticks (100-ns units since 0001-01-01) for the nonce + x-app-request-id source
    td = datetime.now() - _DOTNET_EPOCH
    return (td.days * 86400 + td.seconds) * 10_000_000 + td.microseconds * 10


def app_request_id() -> str:
    return str(dotnet_ticks())


def _pkcs7(b: bytes) -> bytes:
    pad = 16 - (len(b) % 16)
    return b + bytes([pad]) * pad


def _nonce() -> bytes:
    n = dotnet_ticks()
    return n.to_bytes((n.bit_length() + 8) // 8, "little", signed=True)


def encrypt(plaintext: bytes) -> bytes:
    nonce = _nonce()
    iv = hashlib.md5(API_SECRET + nonce).digest()
    ct = Cipher(algorithms.AES(_KEY), modes.CBC(iv)).encryptor().update(_pkcs7(plaintext))
    return bytes([len(nonce) + 2]) + len(nonce).to_bytes(3, "big") + nonce + ct


def decrypt(envelope: bytes) -> bytes:
    nlen = int.from_bytes(envelope[1:4], "big")
    nonce, ct = envelope[4 : 4 + nlen], envelope[4 + nlen :]
    iv = hashlib.md5(API_SECRET + nonce).digest()
    pt = Cipher(algorithms.AES(_KEY), modes.CBC(iv)).decryptor().update(ct)
    return pt[: -pt[-1]] if pt else pt


encrypt_request = encrypt
decrypt_response = decrypt


def frame(msg: bytes) -> bytes:
    return b"\x00" + struct.pack(">I", len(msg)) + msg


def unframe(body: bytes) -> bytes:
    if len(body) < 5:
        return b""
    return body[5 : 5 + int.from_bytes(body[1:5], "big")]


def decode_response(body: bytes) -> bytes:
    if len(body) < 5:
        return b""
    msg = body[5 : 5 + int.from_bytes(body[1:5], "big")]
    if body[0] & 1:
        msg = gzip.decompress(msg)
    return decrypt(msg)
