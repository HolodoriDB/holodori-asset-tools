"""Game API request/response crypto + gRPC-web framing.

The game's rpc.api.* services speak ``application/grpc+proto-enc``: each gRPC message is a
5-byte-prefixed frame whose payload is the protobuf body AES-CBC-encrypted under a key derived from
a build constant, with a per-message nonce. These helpers encrypt an outgoing request body and
decrypt an incoming response body, and frame/unframe the gRPC-web envelope.

Reverse-engineered from the game client; ``API_SECRET`` is a constant embedded in the app (not a
holodori.best secret). Mirrors (and supersedes) the backend's holodori_api/proto_enc.py.
"""

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
    # .NET DateTime.Now ticks (100-ns units since 0001-01-01); the nonce + x-app-request-id source
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
    """AES-CBC-encrypt a request body into the length-tagged proto-enc envelope."""
    nonce = _nonce()
    iv = hashlib.md5(API_SECRET + nonce).digest()
    ct = Cipher(algorithms.AES(_KEY), modes.CBC(iv)).encryptor().update(_pkcs7(plaintext))
    return bytes([len(nonce) + 2]) + len(nonce).to_bytes(3, "big") + nonce + ct


def decrypt(envelope: bytes) -> bytes:
    """Reverse of encrypt(): recover the plaintext protobuf body from a proto-enc envelope."""
    nlen = int.from_bytes(envelope[1:4], "big")
    nonce, ct = envelope[4 : 4 + nlen], envelope[4 + nlen :]
    iv = hashlib.md5(API_SECRET + nonce).digest()
    pt = Cipher(algorithms.AES(_KEY), modes.CBC(iv)).decryptor().update(ct)
    return pt[: -pt[-1]] if pt else pt


# plan-facing names
encrypt_request = encrypt
decrypt_response = decrypt


def frame(msg: bytes) -> bytes:
    """Wrap an encrypted message in the 5-byte gRPC-web length prefix (uncompressed flag)."""
    return b"\x00" + struct.pack(">I", len(msg)) + msg


def unframe(body: bytes) -> bytes:
    """Strip the gRPC-web 5-byte prefix, returning the raw (still-encrypted) message bytes."""
    if len(body) < 5:
        return b""
    return body[5 : 5 + int.from_bytes(body[1:5], "big")]


def decode_response(body: bytes) -> bytes:
    """Full inbound path: unframe -> (gunzip if the compressed flag is set) -> decrypt."""
    if len(body) < 5:
        return b""
    msg = body[5 : 5 + int.from_bytes(body[1:5], "big")]
    if body[0] & 1:
        msg = gzip.decompress(msg)
    return decrypt(msg)
