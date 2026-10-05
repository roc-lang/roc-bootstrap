#!/usr/bin/env python3
"""Validate the exact eight release assets before creating a release draft."""

import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("release_validator", Path(__file__).with_name("validate-release.py"))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

if len(sys.argv) != 4:
    sys.exit("usage: check-release-set.py <asset-directory> <source-commit> <flake.lock>")
directory, revision, lock = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
expected = {target + (".zip" if "windows" in target else ".tar.xz") for target in validator.TARGETS}
actual = {path.name for path in directory.iterdir()}
if actual != expected:
    sys.exit(f"release asset mismatch: missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}")
for target in validator.TARGETS:
    suffix = ".zip" if "windows" in target else ".tar.xz"
    validator.validate(directory / (target + suffix), target, revision, lock)
print("validated all eight release assets")
