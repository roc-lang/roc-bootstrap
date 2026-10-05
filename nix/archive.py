#!/usr/bin/env python3
"""Create release archives independent of filesystem metadata and traversal order."""

import argparse
import hashlib
import lzma
from pathlib import Path
import stat
import tarfile
import zipfile


def archive(source: Path, output: Path, target: str) -> Path:
    entries = [source, *sorted(source.rglob("*"), key=lambda p: p.relative_to(source).as_posix())]
    windows = "-windows-" in target
    destination = output / (target + (".zip" if windows else ".tar.xz"))

    if windows:
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as result:
            for path in entries:
                relative = path.relative_to(source).as_posix()
                name = target if relative == "." else f"{target}/{relative}"
                info = zipfile.ZipInfo(name + ("/" if path.is_dir() else ""), (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                if path.is_symlink():
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    result.writestr(info, path.readlink().as_posix().encode())
                elif path.is_dir():
                    info.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
                    result.writestr(info, b"")
                else:
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    result.writestr(info, path.read_bytes())
    else:
        with lzma.open(destination, "wb", preset=9 | lzma.PRESET_EXTREME) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.GNU_FORMAT) as result:
                for path in entries:
                    relative = path.relative_to(source).as_posix()
                    name = target if relative == "." else f"{target}/{relative}"
                    info = result.gettarinfo(str(path), arcname=name)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 1
                    info.mode = 0o755 if info.isdir() else 0o777 if info.issym() else 0o644
                    if info.isfile():
                        with path.open("rb") as contents:
                            result.addfile(info, contents)
                    else:
                        result.addfile(info)

    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (output / (target + ".sha256")).write_text(f"{digest}  {destination.name}\n")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    archive(args.source, args.output, args.target)
