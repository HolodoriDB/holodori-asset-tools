from .mask import mask

MAGIC = b"QUAVMAGIC"
HEADER_LEN = 256


def decrypt(data: bytes, name: str) -> bytes:
    if data[: len(MAGIC)] != MAGIC:
        return data
    m = mask(name)
    ml = len(m)
    out = bytearray(data)
    for i in range(min(HEADER_LEN, len(out) - len(MAGIC))):
        out[len(MAGIC) + i] ^= m[i % ml]
    return bytes(out[len(MAGIC) :])


def encrypt(data: bytes, name: str) -> bytes:
    if data[: len(MAGIC)] == MAGIC:
        return data
    m = mask(name)
    ml = len(m)
    out = bytearray(MAGIC + data)
    for i in range(min(HEADER_LEN, len(data))):
        out[len(MAGIC) + i] ^= m[i % ml]
    return bytes(out)
