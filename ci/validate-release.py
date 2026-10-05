#!/usr/bin/env python3
"""Validate a complete relocatable Roc dependency release without extracting it."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

TARGETS = (
    "aarch64-linux-musl", "aarch64-macos-none", "aarch64-windows-gnu",
    "arm-linux-musleabihf", "x86-linux-musl", "x86_64-linux-musl",
    "x86_64-macos-none", "x86_64-windows-gnu",
)
COMPONENTS = {
    "zig": "0.17.0", "llvm": "22.1.8", "clang": "22.1.8", "lld": "22.1.8",
    "binaryen": "130", "zlib": "1.3.1", "zstd": "1.5.2",
}


def verify_library(stream, target):
    """Check the first object in an ordinary static archive against the target."""
    if stream.read(8) != b"!<arch>\n":
        raise ValueError("expected a self-contained static archive")
    while header := stream.read(60):
        if len(header) != 60 or header[58:] != b"`\n":
            raise ValueError("malformed static archive header")
        name = header[:16].decode("ascii").strip()
        size = int(header[48:58])
        if size < 0:
            raise ValueError("negative archive member size")
        end = stream.tell() + size + (size % 2)
        if name.startswith("#1/"):
            name_size = int(name[3:])
            if not 0 <= name_size <= min(size, 4096):
                raise ValueError("invalid archive member name size")
            name = stream.read(name_size).rstrip(b"\0").decode("ascii")
        if name in ("/", "//", "/SYM64/") or name.startswith("__.SYMDEF"):
            stream.seek(end)
            continue
        data = stream.read(min(20, end - stream.tell()))
        architecture = target.split("-")[0]
        if "linux" in target:
            expected = {"x86": (1, 3), "x86_64": (2, 62), "arm": (1, 40), "aarch64": (2, 183)}[architecture]
            if len(data) < 20 or data[:4] != b"\x7fELF" or data[5] not in (1, 2):
                raise ValueError("expected an ELF object")
            actual = (data[4], int.from_bytes(data[18:20], "little" if data[5] == 1 else "big"))
            if actual != expected:
                raise ValueError(f"ELF architecture mismatch: {actual} != {expected}")
        elif "macos" in target:
            expected = {"x86_64": 0x01000007, "aarch64": 0x0100000C}[architecture]
            if len(data) < 8 or data[:4] != b"\xcf\xfa\xed\xfe" or int.from_bytes(data[4:8], "little") != expected:
                raise ValueError("Mach-O architecture mismatch")
        else:
            expected = {"x86_64": 0x8664, "aarch64": 0xAA64}[architecture]
            # COFF bigobj places the machine after its signature and version.
            machine = data[6:8] if data[:4] == b"\0\0\xff\xff" else data[:2]
            if int.from_bytes(machine, "little") != expected:
                raise ValueError("COFF architecture mismatch")
        return
    raise ValueError("static archive contains no object files")


def validate(asset, target, revision, lock=None):
    suffix = ".zip" if "windows" in target else ".tar.xz"
    if asset.name != target + suffix:
        raise ValueError(f"expected {target + suffix}, got {asset.name}")
    if suffix == ".zip":
        archive = zipfile.ZipFile(asset)
        entries = archive.infolist()
        names = [entry.filename.rstrip("/") for entry in entries]
        read = archive.read
        open_member = archive.open
        for entry in entries:
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"symlink in release: {entry.filename}")
    else:
        archive = tarfile.open(asset, "r:xz")
        entries = archive.getmembers()
        names = [entry.name.rstrip("/") for entry in entries]
        for entry in entries:
            if not (entry.isfile() or entry.isdir()):
                raise ValueError(f"non-regular release entry: {entry.name}")

        def read(name):
            stream = archive.extractfile(name)
            if stream is None:
                raise ValueError(f"not a file: {name}")
            return stream.read()

        open_member = archive.extractfile

    try:
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive member")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != target:
                raise ValueError(f"unsafe or incorrectly rooted member: {name}")
            if "\\" in name:
                raise ValueError(f"non-portable archive path: {name}")
        metadata = json.loads(read(f"{target}/roc-deps-build.json"))
        expected = {"schemaVersion": 1, "sourceRevision": revision, "sourceDirty": False,
                    "components": COMPONENTS, "target": target, "cpu": "baseline"}
        for key, value in expected.items():
            if metadata.get(key) != value:
                raise ValueError(f"metadata {key}: expected {value!r}, got {metadata.get(key)!r}")
        if metadata.get("builderSystem") not in ("x86_64-linux", "aarch64-linux"):
            raise ValueError("invalid builder system")
        if not re.fullmatch(r"[0-9a-f]{40}", metadata.get("nixpkgsRevision", "")):
            raise ValueError("invalid nixpkgs revision")
        if not re.fullmatch(r"[0-9a-f]{64}", metadata.get("flakeLockSha256", "")):
            raise ValueError("invalid flake lock digest")
        if lock is not None:
            data = lock.read_bytes()
            if hashlib.sha256(data).hexdigest() != metadata["flakeLockSha256"]:
                raise ValueError("flake lock digest mismatch")
            if json.loads(data)["nodes"]["nixpkgs"]["locked"]["rev"] != metadata["nixpkgsRevision"]:
                raise ValueError("nixpkgs revision mismatch")
        required = ("include/llvm-c/Core.h", "include/lld/Common/Driver.h",
                    "include/binaryen-c.h", "include/zlib.h", "include/zstd.h")
        for relative in required:
            if f"{target}/{relative}" not in names:
                raise ValueError(f"missing header: {relative}")
        libraries = {PurePosixPath(name).name for name in names if name.startswith(f"{target}/lib/")}
        # Zig's Windows GNU archives may use either the .a or .lib spelling.
        for library in ("LLVMCore", "LLVMSupport", "LLVMPlugins", "LLVMFrontendDirective",
                        "lldCommon", "lldELF", "lldCOFF", "lldMachO", "binaryen", "z", "zstd"):
            alternatives = {f"lib{library}.a", f"{library}.lib", f"lib{library}.lib"}
            if not libraries & alternatives:
                raise ValueError(f"missing static library: {library}")
            filename = sorted(libraries & alternatives)[0]
            with open_member(f"{target}/lib/{filename}") as stream:
                verify_library(stream, target)
        for name in names:
            relative = PurePosixPath(name).relative_to(target)
            if relative.parts and relative.parts[0] == "lib" and re.search(r"\.(?:so(?:\..*)?|dylib|dll)$", relative.name):
                raise ValueError(f"shared runtime dependency: {name}")
        return metadata
    finally:
        archive.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--flake-lock", type=Path)
    args = parser.parse_args()
    try:
        validate(args.asset, args.target, args.source_revision, args.flake_lock)
    except (ValueError, KeyError, OSError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, f"invalid release: {error}\n")
    print(f"validated {args.asset.name}")


if __name__ == "__main__":
    main()
