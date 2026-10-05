"""Check both archive formats ignore timestamp, permission and creation order."""

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import tarfile
import zipfile


sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("archive", sys.argv[1])
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    first, second = root / "first", root / "second"
    contents = {
        "include/nested/api.h": b"/* interface */\n",
        "lib/libfixture.a": b"fixture archive\n",
        "roc-deps-build.json": b'{"schemaVersion":1}\n',
    }
    for source, entries, modified, mode in (
        (first, list(contents), 1000, 0o600),
        (second, list(reversed(contents)), 2000, 0o444),
    ):
        for name in entries:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents[name])
            os.utime(path, (modified, modified))
            path.chmod(mode)
    for target in ("x86_64-linux-musl", "x86_64-windows-gnu"):
        result_one, result_two = root / "output-one", root / "output-two"
        result_one.mkdir(exist_ok=True)
        result_two.mkdir(exist_ok=True)
        one = archive.archive(first, result_one, target)
        two = archive.archive(second, result_two, target)
        assert one.read_bytes() == two.read_bytes(), target
        checksum = (result_one / (target + ".sha256")).read_text()
        assert checksum == f"{hashlib.sha256(one.read_bytes()).hexdigest()}  {one.name}\n"
        if "windows" in target:
            with zipfile.ZipFile(one) as package:
                members = {entry.filename for entry in package.infolist() if not entry.is_dir()}
                assert members == set(contents)
                assert all(package.read(name) == value for name, value in contents.items())
        else:
            with tarfile.open(one, "r:xz") as package:
                members = {entry.name for entry in package.getmembers() if entry.isfile()}
                assert members == set(contents)
                assert all(package.extractfile(name).read() == value for name, value in contents.items())
print("tar.xz and zip normalization checks passed")
