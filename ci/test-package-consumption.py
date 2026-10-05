#!/usr/bin/env python3
"""Verify release archives through Zig's standalone fetch and dependency paths.

Uses only tiny synthetic inputs, a loopback HTTP server, and private caches.
No Roc, LLVM, or target compiler build is required.
"""

import argparse
from contextlib import contextmanager
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading


TARGETS = ("x86_64-linux-musl", "x86_64-windows-gnu")


@contextmanager
def workspace(requested):
    if requested is None:
        with tempfile.TemporaryDirectory(prefix="roc-package-consumption-") as temporary:
            yield Path(temporary)
    else:
        requested.mkdir(parents=True, exist_ok=True)
        if any(requested.iterdir()):
            raise ValueError("--work-dir must be empty")
        yield requested


def check(zig, archive_script, root):
    served = root / "archives"
    served.mkdir()
    global_cache = root / "global-cache"
    env = os.environ.copy()
    env["ZIG_GLOBAL_CACHE_DIR"] = str(global_cache)
    commands = []
    requests = []
    cases = []

    def run(label, argv, cwd, succeeds=True, diagnostic=None):
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        (root / (label + ".stdout")).write_text(result.stdout)
        (root / (label + ".stderr")).write_text(result.stderr)
        commands.append({"label": label, "argv": argv, "cwd": str(cwd),
                         "exitCode": result.returncode, "expectedSuccess": succeeds})
        (root / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if (result.returncode == 0) != succeeds or (diagnostic and diagnostic not in result.stderr):
            raise RuntimeError(f"{label} failed its expected outcome:\n{result.stdout}\n{result.stderr}")
        return result

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append(self.path)
            super().do_GET()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(served)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for target in TARGETS:
            consumer = root / target
            consumer.mkdir()
            source = consumer / "source"
            expected = {
                "include/fixture.h": b"/* package-consumption fixture */\n",
                "lib/libfixture.a": b"!<arch>\n",
                "roc-deps-build.json": json.dumps({"schemaVersion": 1, "target": target},
                                                  sort_keys=True).encode() + b"\n",
            }
            for name, data in expected.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            run(target + "-archive", [sys.executable, str(archive_script), "--source", str(source),
                                     "--output", str(served), "--target", target], root)
            suffix = ".zip" if "-windows-" in target else ".tar.xz"
            url = f"http://127.0.0.1:{server.server_port}/{target}{suffix}"
            fetched = run(target + "-fetch", [str(zig), "fetch", url], root)
            package_hash = fetched.stdout.strip()
            if not package_hash.startswith("N-V-") or len(package_hash) != 48:
                raise RuntimeError(f"unexpected Zig package hash: {package_hash!r}")

            # These are the same dependency paths Roc's downloaded LLVM bundle uses.
            (consumer / "build.zig").write_text(
                'const std = @import("std");\n'
                'pub fn build(b: *std.Build) void {\n'
                '    const deps = b.dependency("roc_deps", .{});\n'
                '    const probe = b.addSystemCommand(&.{' + json.dumps(sys.executable) + ', "probe.py"});\n'
                '    probe.stdio = .inherit;\n'
                '    probe.addDirectoryArg(deps.path(""));\n'
                '    probe.addDirectoryArg(deps.path("include"));\n'
                '    probe.addDirectoryArg(deps.path("lib"));\n'
                '    probe.addFileArg(deps.path("roc-deps-build.json"));\n'
                '    b.step("probe", "Verify packaged dependency paths and bytes").dependOn(&probe.step);\n'
                '}\n')
            (consumer / "probe.py").write_text(
                "import json,pathlib,sys\n"
                "root,include,lib,metadata=map(pathlib.Path,sys.argv[1:])\n"
                "expected=" + repr({name: data.hex() for name, data in expected.items()}) + "\n"
                "paths={'include/fixture.h':include/'fixture.h','lib/libfixture.a':lib/'libfixture.a',"
                "'roc-deps-build.json':metadata}\n"
                "assert include.resolve()==(root/'include').resolve()\n"
                "assert lib.resolve()==(root/'lib').resolve()\n"
                "assert metadata.resolve()==(root/'roc-deps-build.json').resolve()\n"
                "assert sorted(p.name for p in root.iterdir())==['include','lib','roc-deps-build.json']\n"
                "for name,path in paths.items():\n"
                " assert path.read_bytes()==bytes.fromhex(expected[name]), 'packaged bytes differ: '+name\n"
                "print(json.dumps({'paths':[str(p.resolve()) for p in [root,include,lib,metadata]],"
                "'metadata':json.loads(metadata.read_text()),'bytes':'verified'}))\n")

            def manifest(value):
                (consumer / "build.zig.zon").write_text(
                    '.{.name=.roc_deps_probe,.version="0.0.0",.fingerprint=0x143f8f8cc0952c25,'
                    '.minimum_zig_version="0.17.0",.dependencies=.{.roc_deps=.{.url=' + json.dumps(url) +
                    ',.hash=' + json.dumps(value) + '}},.paths=.{"build.zig","build.zig.zon","probe.py"}}\n')

            def build(label, package_dir, succeeds=True, diagnostic=None):
                # Zig 0.17 can retain dependency paths in a cached graph when
                # only --pkg-dir changes. Configure each package root separately.
                result = run(target + "-" + label,
                             [str(zig), "build", "probe", "--cache-dir",
                              str(consumer / ("cache-" + package_dir.name)),
                              "--pkg-dir", str(package_dir), "--summary", "all"],
                             consumer, succeeds, diagnostic)
                if succeeds:
                    probe = json.loads(result.stdout)
                    if Path(probe["paths"][0]) != (package_dir / package_hash).resolve():
                        raise RuntimeError("consumer retained a different package directory")
                return result

            manifest(package_hash)
            count_before = len(requests)
            first_packages = consumer / "packages-first"
            second_packages = consumer / "packages-fresh"
            build("preseeded-consumer", first_packages)
            build("unchanged-repeat", first_packages)
            build("fresh-package-dir", second_packages)
            build("fresh-unchanged-repeat", second_packages)
            if len(requests) != count_before:
                raise RuntimeError("consumer downloaded instead of using the standalone fetch cache")

            # Validate the global representation, rather than trusting only filenames.
            with tarfile.open(global_cache / "p" / (package_hash + ".tar.gz")) as cached:
                for name, data in expected.items():
                    entry = cached.extractfile(package_hash + "/" + name)
                    if entry is None or entry.read() != data:
                        raise RuntimeError("global package cache bytes differ: " + name)

            # A valid but incorrect content hash must fail, even with the correct package cached.
            wrong_hash = package_hash[:24] + ("A" if package_hash[24] != "A" else "B") + package_hash[25:]
            manifest(wrong_hash)
            build("wrong-hash-control", consumer / "packages-wrong", False, "hash mismatch")
            manifest(package_hash)

            # The path probe must detect content corruption, not merely missing files.
            header = first_packages / package_hash / "include" / "fixture.h"
            original = header.read_bytes()
            header.write_bytes(b"corrupt fixture header\n")
            try:
                build("wrong-bytes-control", first_packages, False, "packaged bytes differ")
            finally:
                header.write_bytes(original)
            build("restored-bytes", first_packages)
            cases.append({"target": target, "format": suffix, "packageHash": package_hash,
                          "preseededConsumer": "pass", "freshPackageDirectory": "pass",
                          "unchangedRepeats": "pass", "wrongHashControl": "rejected",
                          "wrongBytesControl": "rejected", "restoredBytes": "pass"})
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    result = {"status": "pass", "cases": cases, "httpRequests": requests,
              "commandCount": len(commands)}
    (root / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", required=True, type=Path)
    parser.add_argument("--archive-script", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path, help="retain logs in an empty directory")
    args = parser.parse_args()
    try:
        with workspace(args.work_dir.resolve() if args.work_dir else None) as root:
            result = check(args.zig.resolve(), args.archive_script.resolve(), root)
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"package consumption check failed: {error}\n")


if __name__ == "__main__":
    main()
