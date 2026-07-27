def mask(name: str) -> bytes:
    n = len(name)
    m = bytearray(2 * n)
    for i, ch in enumerate(name):
        c = ord(ch) & 0xFF
        m[2 * i] = c
        m[2 * n - 1 - 2 * i] = ~c & 0xFF
    h = 0x7C
    for b in m:
        h = (((h & 1) << 7 | h >> 1) ^ b) & 0xFF
    return bytes(x ^ h for x in m)
