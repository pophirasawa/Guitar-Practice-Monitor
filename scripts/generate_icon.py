import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "app.ico"
SIZE = 256


def png_chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def make_png(size):
    rows = []
    cx = cy = (size - 1) / 2
    for y in range(size):
        row = bytearray()
        for x in range(size):
            dx = (x - cx) / cx
            dy = (y - cy) / cy
            distance = math.sqrt(dx * dx + dy * dy)
            if distance > 0.94:
                row.extend((0, 0, 0, 0))
                continue

            glow = max(0.0, 1.0 - distance)
            r = int(8 + 36 * glow)
            g = int(16 + 150 * glow)
            b = int(24 + 104 * glow)
            a = 255

            wave = math.sin((x / size) * math.tau * 3.2)
            band = abs(dy - wave * 0.16)
            if band < 0.055:
                r, g, b = 77, 240, 162
            if abs(dx) < 0.10 and abs(dy) < 0.42:
                r, g, b = max(r, 255), max(g, 209), max(b, 102)

            row.extend((r, g, b, a))
        rows.append(b"\x00" + bytes(row))

    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )


def main():
    OUT.parent.mkdir(exist_ok=True)
    png = make_png(SIZE)
    header = struct.pack("<HHH", 0, 1, 1)
    directory = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 6 + 16)
    OUT.write_bytes(header + directory + png)
    print(OUT)


if __name__ == "__main__":
    main()
