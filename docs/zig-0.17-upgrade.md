# Zig 0.17 upgrade and release validation

The upgrade starts from `llvm-21.1.8-scaling-2`
(`6408d92578c9f405d4914365ddec835094c68558`). The verified official bootstrap
archive provides Zig 0.17.0 and LLVM/Clang/LLD 22.1.8. The import checksum and
retained Roc patches are documented in [../llvm/ROC_PATCHES.md](../llvm/ROC_PATCHES.md).

## Release sequence

1. Review and merge the bootstrap source, Nix, and release workflow changes.
2. Push `zig-0.17.0` at the reviewed commit to run the release workflow.
3. Review its eight target builds, metadata checks, provenance checks, and the
   x86_64 Linux rebuild comparison. Build measurements and native-tool closure
   export/import costs are saved as workflow artifacts.
4. Publish the resulting draft. Until the workflow has run, build provenance
   and cross-target release validation remain unverified.
5. Fetch each published archive with Zig 0.17, record its Zig package hash in
   Roc's `build.zig.zon`, and regenerate `src/build.zig.zon.nix`. Link the build
   run in Roc's upgrade PR and verify every pinned asset's provenance.
6. Merge Roc after its correctness and build-cache checks pass.

Local Roc development can use `-Droc-deps-path=<complete bundle>` before the
release is published. A complete bundle has LLVM, LLD, Binaryen, zlib, and zstd
under `include/` and `lib/`. A partial LLVM-only prefix does not exercise the
same configuration as Roc's default release dependencies.

The future release workflow addresses
[roc-lang/roc#11896](https://github.com/roc-lang/roc/issues/11896). Historical
archives are not rebuilt by this upgrade. SLSA build provenance binds future
archive digests to the workflow, tag, and source commit. It is checked separately
from the release attestation and the Zig package hash.

```sh
bash ci/verify-provenance.sh x86_64-linux-musl.tar.xz zig-0.17.0 <source-commit>
python3 ci/validate-release.py --asset x86_64-linux-musl.tar.xz \
  --target x86_64-linux-musl --source-revision <source-commit> --flake-lock flake.lock
```

## Cache and reproducibility checks

Nix compile derivations must remain identical after README or workflow edits.
Editing Binaryen must change its derivation while preserving native LLVM, host
Zig, and target LLVM. The lock and Git revision belong in final bundle metadata,
so changing source identity does not invalidate otherwise identical compilation.

The initial release checks one full x86_64 Linux rebuild, including native
LLVM, host Zig, target libraries, and archive assembly. This is an expensive
check of the new recipe. It does not establish bit-for-bit reproducibility for
every cross target. Routine iteration should use warm-cache and declared-input
invalidation checks; further full rebuilds are useful when the toolchain or
recipes change.

Roc performance measurements use `ReleaseFast`, `-Dstrip=false`, four jobs,
separate Zig caches, an isolated Roc application cache, and the same source
revision for the pre-upgrade baseline. Dependency download time is reported
separately where possible. Cold configure, cold compile, warm rebuild, and
generated-file work are distinct measurements. Correctness tests use Debug or
ReleaseSafe separately. No speedup is claimed until both versions are measured.

The Roc validation matrix covers unchanged warm builds; production/test-only
edits; imported Roc module edit/add/delete; missing installed/generated files;
mode and target switching; independent concurrent build directories; granular
MiniCI steps; application-cache preservation on an unchanged compiler; and
application-cache invalidation after a dirty semantic compiler change with the
same Git HEAD. Generated assets must stay in build caches rather than rewriting
source files.

## Local validation record

Implementation and validation are in progress. The source import and retained
patch audit are complete. Full LLVM assertion-harness results, Nix stage builds,
Roc correctness tests, measured cache behavior, release asset hashes, and GitHub
attestations are recorded here as those checks finish.

Checks completed locally:

* All flake outputs evaluate on both Linux builder architectures. The archive
  normalization check passes in the Nix sandbox.
* Isolated input edits verify the cache boundary across 35 compilation
  derivations: documentation/workflow and provenance-only edits reuse all
  compilation; Binaryen edits change only its eight compilation derivations.
* Six release-validator policy tests pass. Workflow actionlint and provenance
  script shellcheck pass. These are local definition checks, not attestations.
* Roc's LLVM vendor tests pass in Zig 0.17 `ReleaseSafe`, covering target layout,
  ordered entry allocas, bitcode serialization, and successive module assembly.
* The compiler compatibility host tool passes seven filesystem integration
  tests in `ReleaseSafe`: dirty edits and reverts, import membership, dependency
  and exact toolchain changes, semantic options, path independence, and stable
  dependency ordering. Runtime cache wiring is still being validated.

The initial Roc 0.16 baseline is from `ce7b298cacaee79e7dbcaba3b6cde6d8f3d73bf9`
on the same host, using four build jobs. Cold configure (`zig build --help` with
empty private Zig caches) took **64.93 seconds**. After configure, the first
`zig build roc -Doptimize=ReleaseFast -Dstrip=false` took **758.68 seconds**, with
peak RSS **19,652,156 KiB**. The unchanged warm build took **0.21 seconds**.
All 221 steps succeeded; the warm build reused compilation and still executed
the global Roc cache-clearing step. No 0.17 timing comparison is available yet.
