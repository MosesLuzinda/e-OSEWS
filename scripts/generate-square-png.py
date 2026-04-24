import struct
import zlib
from pathlib import Path


def _read_png_rgba8(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path}")

    off = 8
    width = height = None
    idat = bytearray()

    while off < len(data):
        if off + 8 > len(data):
            raise ValueError("Truncated PNG")
        length = struct.unpack(">I", data[off : off + 4])[0]
        off += 4
        ctype = data[off : off + 4]
        off += 4
        chunk = data[off : off + length]
        off += length
        off += 4  # crc

        if ctype == b"IHDR":
            w, h, bit_depth, color_type, comp, filt, inter = struct.unpack(">IIBBBBB", chunk)
            if inter != 0:
                raise ValueError("Interlaced PNGs are not supported by this generator")
            if bit_depth != 8 or color_type != 6:
                raise ValueError("Expected RGBA8 PNG (color type 6, bit depth 8)")
            width, height = w, h
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break

    if width is None or height is None:
        raise ValueError("Missing IHDR")

    raw = zlib.decompress(bytes(idat))

    bpp = 4
    stride = width * bpp
    expected = height * (1 + stride)
    if len(raw) != expected:
        raise ValueError(f"Unexpected decompressed scanline size: got {len(raw)}, expected {expected}")

    def paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    pixels: list[tuple[int, int, int, int]] = []
    prev = bytearray(stride)

    for y in range(height):
        f = raw[y * (1 + stride)]
        scan = bytearray(raw[y * (1 + stride) + 1 : y * (1 + stride) + 1 + stride])
        if f == 0:
            recon = scan
        elif f == 1:  # Sub
            for i in range(stride):
                left = recon[i - bpp] if i >= bpp else 0
                scan[i] = (scan[i] + left) & 0xFF
            recon = scan
        elif f == 2:  # Up
            for i in range(stride):
                scan[i] = (scan[i] + prev[i]) & 0xFF
            recon = scan
        elif f == 3:  # Average
            for i in range(stride):
                left = recon[i - bpp] if i >= bpp else 0
                up = prev[i]
                scan[i] = (scan[i] + ((left + up) // 2)) & 0xFF
            recon = scan
        elif f == 4:  # Paeth
            for i in range(stride):
                left = recon[i - bpp] if i >= bpp else 0
                up = prev[i]
                up_left = prev[i - bpp] if i >= bpp else 0
                scan[i] = (scan[i] + paeth(left, up, up_left)) & 0xFF
            recon = scan
        else:
            raise ValueError(f"Unsupported PNG filter: {f}")

        prev = recon
        for x in range(width):
            i = x * bpp
            pixels.append((recon[i], recon[i + 1], recon[i + 2], recon[i + 3]))

    return width, height, pixels


def _write_png_rgba8(path: Path, width: int, height: int, rgba_rows: list[bytes]) -> None:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    for row in rgba_rows:
        raw.append(0)  # filter None
        raw.extend(row)

    compressed = zlib.compress(bytes(raw), level=9)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "mobile-app" / "assets" / "logo1.png"
    out_icon = repo_root / "mobile-app" / "assets" / "icon.png"
    out_foreground = repo_root / "mobile-app" / "assets" / "adaptive-icon-foreground.png"

    sw, sh, src_pixels = _read_png_rgba8(src)

    # Expo requires square icons. We letterbox the wide logo onto a square canvas.
    size = max(sw, sh)
    bg = (11, 23, 56, 255)  # matches splash backgroundColor-ish (#0b1738)

    canvas = [[bg for _ in range(size)] for _ in range(size)]

    ox = (size - sw) // 2
    oy = (size - sh) // 2

    idx = 0
    for y in range(sh):
        for x in range(sw):
            canvas[oy + y][ox + x] = src_pixels[idx]
            idx += 1

    rows: list[bytes] = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            r, g, b, a = canvas[y][x]
            row.extend([r, g, b, a])
        rows.append(bytes(row))

    _write_png_rgba8(out_icon, size, size, rows)
    _write_png_rgba8(out_foreground, size, size, rows)


if __name__ == "__main__":
    main()
