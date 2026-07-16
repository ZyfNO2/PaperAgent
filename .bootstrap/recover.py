from __future__ import annotations

import base64
import hashlib
import os
import zlib
from pathlib import Path, PurePosixPath

EXPECTED = "3a996bc1f69fe419bc478c2e486487aeb5f1ffa3d14383e75d93f2379ef15a97"


def parse_number(field: bytes) -> int:
    if field and field[0] & 0x80:
        return int.from_bytes(field, byteorder="big", signed=True)
    cleaned = field.rstrip(b"\0 ").strip()
    return int(cleaned or b"0", 8)


def parse_pax(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    offset = 0
    while offset < len(data):
        separator = data.find(b" ", offset)
        if separator < 0:
            raise SystemExit("invalid pax record")
        length = int(data[offset:separator])
        if length <= 0 or offset + length > len(data):
            raise SystemExit("invalid pax record length")
        record = data[separator + 1 : offset + length].rstrip(b"\n")
        key, value = record.split(b"=", 1)
        result[key.decode("utf-8")] = value.decode("utf-8")
        offset += length
    return result


def safe_path(name: str) -> Path:
    normalized = PurePosixPath(name)
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise SystemExit(f"unsafe archive path: {name!r}")
    if normalized.parts[0] == ".git":
        raise SystemExit(f"archive attempts to write .git: {name!r}")
    return Path(*normalized.parts)


def decompress_gzip_without_trailer_check(payload: bytes) -> bytes:
    if len(payload) < 18 or payload[:3] != b"\x1f\x8b\x08":
        raise SystemExit("payload is not a supported gzip stream")
    flags = payload[3]
    if flags & 0xE0:
        raise SystemExit("gzip reserved flags are set")
    offset = 10
    if flags & 0x04:
        if offset + 2 > len(payload):
            raise SystemExit("truncated gzip extra header")
        extra_length = int.from_bytes(payload[offset : offset + 2], "little")
        offset += 2 + extra_length
    for flag in (0x08, 0x10):
        if flags & flag:
            terminator = payload.find(b"\0", offset)
            if terminator < 0:
                raise SystemExit("truncated gzip text header")
            offset = terminator + 1
    if flags & 0x02:
        offset += 2
    if offset >= len(payload) - 8:
        raise SystemExit("truncated gzip payload")
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    raw = decompressor.decompress(payload[offset:-8]) + decompressor.flush()
    if not decompressor.eof:
        raise SystemExit("deflate stream did not terminate cleanly")
    print("warning: gzip trailer CRC/size ignored; extracted tree must pass all release gates")
    return raw


def main() -> None:
    parts = sorted(Path(".bootstrap").glob("payload.part*"))
    if not parts:
        raise SystemExit("no bootstrap payload parts found")
    encoded = b"".join(part.read_bytes().strip() for part in parts)
    payload = base64.b64decode(encoded, validate=True)
    actual = hashlib.sha256(payload).hexdigest()
    print(f"payload parts={len(parts)} encoded={len(encoded)} decoded={len(payload)} sha256={actual}")
    if actual != EXPECTED:
        raise SystemExit(f"payload sha256 mismatch: expected={EXPECTED} actual={actual}")

    raw = decompress_gzip_without_trailer_check(payload)
    offset = 0
    entries = 0
    checksum_mismatches = 0
    pending_longname: str | None = None
    global_pax: dict[str, str] = {}
    next_pax: dict[str, str] = {}

    while offset + 512 <= len(raw):
        header = raw[offset : offset + 512]
        if header == b"\0" * 512:
            break
        stored_checksum = parse_number(header[148:156])
        calculated_checksum = sum(header[:148]) + (32 * 8) + sum(header[156:])
        if stored_checksum != calculated_checksum:
            checksum_mismatches += 1

        name = header[0:100].split(b"\0", 1)[0].decode("utf-8", errors="strict")
        prefix = header[345:500].split(b"\0", 1)[0].decode("utf-8", errors="strict")
        if prefix:
            name = f"{prefix}/{name}"
        size = parse_number(header[124:136])
        mode = parse_number(header[100:108])
        typeflag = header[156:157] or b"0"
        data_start = offset + 512
        data_end = data_start + size
        if data_end > len(raw):
            raise SystemExit(f"truncated tar entry: {name!r}")
        data = raw[data_start:data_end]
        offset = data_start + ((size + 511) // 512) * 512

        if typeflag == b"g":
            global_pax.update(parse_pax(data))
            continue
        if typeflag == b"x":
            next_pax = parse_pax(data)
            continue
        if typeflag == b"L":
            pending_longname = data.rstrip(b"\0\n").decode("utf-8")
            continue
        if typeflag in {b"1", b"2", b"3", b"4", b"6", b"7", b"K"}:
            raise SystemExit(f"unsupported archive entry type {typeflag!r}: {name!r}")

        metadata = {**global_pax, **next_pax}
        resolved_name = metadata.get("path") or pending_longname or name
        pending_longname = None
        next_pax = {}
        target = safe_path(resolved_name)

        if typeflag == b"5":
            target.mkdir(parents=True, exist_ok=True)
            entries += 1
            continue
        if typeflag not in {b"0", b"\0"}:
            raise SystemExit(f"unknown archive entry type {typeflag!r}: {resolved_name!r}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        os.chmod(target, mode & 0o777)
        entries += 1

    required = [Path("pyproject.toml"), Path("src/paperagent"), Path("tests")]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"recovered archive missing required paths: {missing}")
    print(
        f"recovered entries={entries} checksum_mismatches={checksum_mismatches} "
        f"uncompressed_bytes={len(raw)}"
    )


if __name__ == "__main__":
    main()
