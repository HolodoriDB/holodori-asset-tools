from .mask import mask

HEADER_LEN = 256
UNITY_SIGNATURE = b"UnityFS"


def _crypt(data: bytes, name: str) -> bytes:
    m = mask(name)
    ml = len(m)
    out = bytearray(data)
    for p in range(min(HEADER_LEN, len(out))):
        out[p] ^= m[p % ml]
    return bytes(out)


def decrypt(data: bytes, name: str) -> bytes:
    if data[: len(UNITY_SIGNATURE)] == UNITY_SIGNATURE:
        return data
    return _crypt(data, name)


def encrypt(data: bytes, name: str) -> bytes:
    if data[: len(UNITY_SIGNATURE)] != UNITY_SIGNATURE:
        return data
    return _crypt(data, name)
