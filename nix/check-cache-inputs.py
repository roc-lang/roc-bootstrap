#!/usr/bin/env python3
"""Verify source filtering by evaluating derivation paths after isolated edits.

Run with `python3 nix/check-cache-inputs.py`. No compilation or working-tree
edits are performed. The temporary tree uses hard links when available and
atomically replaces edited files, so the original source stays untouched.
"""

import json
import errno
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


repository = Path(__file__).resolve().parent.parent


def nix(*args):
    return json.loads(subprocess.check_output(["nix", *args], text=True))


with tempfile.TemporaryDirectory(prefix=".cache-inputs-", dir=repository) as temporary:
    fixture = Path(temporary) / "source"
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=repository).decode().split("\0")
    for name in filter(None, tracked):
        original, destination = repository / name, fixture / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if original.is_symlink():
            destination.symlink_to(original.readlink())
        else:
            try:
                os.link(original, destination)
            except OSError as error:
                if error.errno != errno.EXDEV:
                    raise
                shutil.copy2(original, destination)

    def paths(revision="0" * 40):
        expression = f'''
          let
            flake = builtins.getFlake {json.dumps(str(repository))};
            self = {{ outPath = builtins.toPath {json.dumps(str(fixture))}; rev = "{revision}"; }};
            nixpkgs = flake.inputs.nixpkgs;
            pkgs = import nixpkgs {{ system = "x86_64-linux"; }};
            result = import (self.outPath + "/nix/packages.nix") {{ inherit self nixpkgs pkgs; system = "x86_64-linux"; }};
          in builtins.mapAttrs (_: package: package.drvPath) result.packages
        '''
        return nix("eval", "--json", "--impure", "--expr", expression)

    def replace(name, content):
        destination = fixture / name
        destination.parent.chmod(0o755)
        destination.unlink(missing_ok=True)
        destination.write_bytes(content)

    baseline = paths()
    compilation = [name for name in baseline if name.startswith(("native-llvm", "host-zig", "host-tools", "zlib-", "zstd-", "llvm-", "binaryen-"))]
    replace("README.md", b"Documentation-only cache invalidation check\n")
    replace(".github/workflows/release-roc-deps.yml", b"# Workflow-only cache invalidation check\n")
    documentation = paths()
    assert documentation == baseline, "Documentation changed a derivation"
    replace("llvm/ROC_PATCHES.md", b"Patch audit cache invalidation check\n")
    replace("llvm/test/roc-cache-inputs.ll", b"; Regression fixture cache invalidation check\n")
    replace("llvm/unittests/roc-cache-inputs.cpp", b"// Unit fixture cache invalidation check\n")
    patch_audit = paths()
    assert patch_audit == baseline, "LLVM patch audit or disabled tests changed a derivation"
    changed_revision = paths("1" * 40)
    assert all(changed_revision[name] == baseline[name] for name in compilation), "Provenance invalidated compilation"
    assert changed_revision["deps-x86_64-linux-musl"] != baseline["deps-x86_64-linux-musl"], "Provenance did not update assembly"
    lock_contents = (fixture / "flake.lock").read_bytes()
    replace("flake.lock", lock_contents + b"\n")
    changed_lock_digest = paths()
    assert all(changed_lock_digest[name] == baseline[name] for name in compilation), "Lock digest invalidated compilation"
    assert changed_lock_digest["deps-x86_64-linux-musl"] != baseline["deps-x86_64-linux-musl"], "Lock digest did not update assembly"
    replace("flake.lock", lock_contents)
    binaryen_file = fixture / "binaryen/CMakeLists.txt"
    replace("binaryen/CMakeLists.txt", binaryen_file.read_bytes() + b"\n# Binaryen input invalidation check\n")
    binaryen = paths()
    assert all(binaryen[name] == baseline[name] for name in compilation if not name.startswith("binaryen-")), "Binaryen invalidated another compilation stage"
    assert all(binaryen[name] != baseline[name] for name in compilation if name.startswith("binaryen-")), "Binaryen edit was missed"
    assert binaryen["deps-x86_64-linux-musl"] != baseline["deps-x86_64-linux-musl"], "Binaryen edit did not update assembly"
    print(f"Cache input checks passed across {len(compilation)} compilation derivations")
