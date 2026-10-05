#!/usr/bin/env python3
"""Release validation policy tests using synthetic bundles."""

import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("validator", Path(__file__).with_name("validate-release.py"))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
REVISION = "a" * 40


class ReleasePolicy(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def bundle(self, target="x86_64-linux-musl", changes=None, extra=None, omit=None):
        metadata = {"schemaVersion": 1, "sourceRevision": REVISION, "sourceDirty": False,
                    "components": validator.COMPONENTS, "target": target, "cpu": "baseline",
                    "builderSystem": "x86_64-linux", "nixpkgsRevision": "b" * 40,
                    "flakeLockSha256": "c" * 64}
        metadata.update(changes or {})
        files = {"roc-deps-build.json": json.dumps(metadata).encode()}
        for header in ("llvm-c/Core.h", "lld/Common/Driver.h", "binaryen-c.h", "zlib.h", "zstd.h"):
            files[f"include/{header}"] = b"synthetic header"
        for library in ("LLVMCore", "LLVMSupport", "LLVMDTLTO", "LLVMPlugins", "LLVMFrontendDirective",
                        "lldCommon", "lldELF", "lldCOFF", "lldMachO", "binaryen", "z", "zstd"):
            if "windows" in target:
                contents = (0xAA64 if target.startswith("aarch64") else 0x8664).to_bytes(2, "little") + bytes(18)
            else:
                contents = b"\x7fELF\x02\x01" + bytes(12) + (62).to_bytes(2, "little")
            header = b"object.o/       " + b"0           " + b"0     " + b"0     " + b"100644  " + str(len(contents)).encode().ljust(10) + b"`\n"
            files[f"lib/lib{library}.a"] = b"!<arch>\n" + header + contents
        if omit:
            del files[omit]
        files.update(extra or {})
        suffix = ".zip" if "windows" in target else ".tar.xz"
        asset = Path(self.directory.name) / (target + suffix)
        if suffix == ".zip":
            with zipfile.ZipFile(asset, "w") as archive:
                for name, contents in files.items():
                    archive.writestr(name, contents)
        else:
            with tarfile.open(asset, "w:xz") as archive:
                for name, contents in files.items():
                    entry = tarfile.TarInfo(name)
                    entry.size = len(contents)
                    archive.addfile(entry, io.BytesIO(contents))
        return asset

    def test_accepts_both_release_formats(self):
        for target in ("x86_64-linux-musl", "aarch64-windows-gnu"):
            with self.subTest(target=target):
                validator.validate(self.bundle(target), target, REVISION)

    def test_rejects_wrong_source_and_dirty_builds(self):
        for changes in ({"sourceRevision": "d" * 40}, {"sourceDirty": True}, {"cpu": "native"}, {"components": {}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validator.validate(self.bundle(changes=changes), "x86_64-linux-musl", REVISION)

    def test_rejects_incomplete_bundle(self):
        for library in ("binaryen", "LLVMDTLTO", "LLVMPlugins", "LLVMFrontendDirective"):
            with self.subTest(library=library), self.assertRaisesRegex(ValueError, "missing static library"):
                validator.validate(self.bundle(omit=f"lib/lib{library}.a"), "x86_64-linux-musl", REVISION)

    def test_rejects_path_escape(self):
        for name in ("../outside", "/absolute", "include/../../outside", "wrong-root/header"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validator.validate(self.bundle(extra={name: b"invalid"}), "x86_64-linux-musl", REVISION)

    def test_rejects_wrapped_package_layout(self):
        for target in ("x86_64-linux-musl", "aarch64-windows-gnu"):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "package root"):
                validator.validate(self.bundle(target, extra={f"{target}/include/api.h": b"nested"}), target, REVISION)

    def test_rejects_symlink(self):
        asset = self.bundle()
        with tarfile.open(asset, "r:xz") as archive:
            members = [(entry, archive.extractfile(entry).read()) for entry in archive]
        with tarfile.open(asset, "w:xz") as archive:
            for entry, contents in members:
                archive.addfile(entry, io.BytesIO(contents))
            link = tarfile.TarInfo("lib/external")
            link.type = tarfile.SYMTYPE
            link.linkname = "/nix/store/unavailable/lib.a"
            archive.addfile(link)
        with self.assertRaises(ValueError):
            validator.validate(asset, "x86_64-linux-musl", REVISION)

    def test_rejects_wrong_lock(self):
        lock = Path(self.directory.name) / "flake.lock"
        lock.write_text("{}")
        with self.assertRaises(ValueError):
            validator.validate(self.bundle(), "x86_64-linux-musl", REVISION, lock)

    def test_rejects_wrong_architecture(self):
        asset = self.bundle()
        with tarfile.open(asset, "r:xz") as archive:
            members = [(entry, archive.extractfile(entry).read()) for entry in archive]
        with tarfile.open(asset, "w:xz") as archive:
            for entry, contents in members:
                if entry.name.endswith("libbinaryen.a"):
                    contents = contents[:-2] + (183).to_bytes(2, "little")
                archive.addfile(entry, io.BytesIO(contents))
        with self.assertRaisesRegex(ValueError, "architecture mismatch"):
            validator.validate(asset, "x86_64-linux-musl", REVISION)


if __name__ == "__main__":
    unittest.main()
