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
   Roc's `build.zig.zon`, and regenerate `build.zig.zon.nix`. Link the build
   run and recorded content hashes in Roc's upgrade PR.
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

Routine builds, dependency fetches, and CI checks rely on reviewed content
hashes and locked Nix inputs. They do not query GitHub's attestation API.
Provenance verification belongs to release publication and explicit audits;
it is not a prerequisite for building or checking a cached dependency bundle.
Roc's application-cache compatibility digest is also computed locally from
declared compiler inputs, toolchain bytes, and effective build options.

```sh
# Explicit release provenance audit (requires the GitHub attestation service).
bash ci/verify-provenance.sh x86_64-linux-musl.tar.xz zig-0.17.0 <source-commit>
# Local metadata and archive validation (no attestation API).
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
check of the new recipe. The native packages are built independently in the
host-tools and x86 target jobs and compared using recorded NAR hashes; their
development outputs are not transferred with the small runtime closure.
Existing target-stage and assembly outputs use Nix's `--rebuild` comparison.
It does not establish bit-for-bit reproducibility for
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

Implementation and validation are in progress. The source import, retained
patch audit, and LLVM assertion harness are complete. Nix stage builds, Roc
correctness tests, measured cache behavior, release asset hashes, and GitHub
attestations are recorded here as those checks finish.

Checks completed locally:

* The four retained LLVM patches pass an assertion-enabled LLVM 22.1.8 harness:
  CodeGen (260), IR (852), Utils (175), and Vectorize (68) unit tests pass,
  including the exhaustive live-range regression. The Inline, SLPVectorizer,
  CodeGenPrepare, and Generic DebugInfo lit suites pass 1,236 tests, with one
  expected failure and 347 unsupported tests. The X86-only harness skips 48
  architecture-specific unit tests. The first lit run caught an LLVM 22 debug
  record insertion regression in the bounded address-user search; returning
  head-exclusive instruction iterators fixed it without changing the search's
  scaling. The upstream debug regression is retained in this repository.
* All flake outputs evaluate on both Linux builder architectures. The archive
  normalization check passes in the Nix sandbox.
* Isolated input edits verify the cache boundary across 35 compilation
  derivations: documentation/workflow and provenance-only edits reuse all
  compilation; Binaryen edits change only its eight compilation derivations.
* Seven release-validator policy tests pass, including static-library target
  architecture checks and rejection of missing LLVM 22's newly split
  `LLVMDTLTO`, `LLVMPlugins`, and `LLVMFrontendDirective` libraries. Full Roc
  eval linking exposed the missing DTLTO link dependency of LLVM 22's COFF
  driver; the bundle already contains it and Roc's ordered link list now
  includes it. Workflow actionlint and provenance
  script shellcheck pass. These are local definition checks, not attestations.
* Roc's LLVM vendor tests pass in Zig 0.17 `ReleaseSafe`, covering target layout,
  ordered entry allocas, bitcode serialization, and successive module assembly.
* The compiler compatibility host tool passes seven filesystem integration
  tests in `ReleaseSafe`: dirty edits and reverts, import membership, dependency
  and exact toolchain changes, semantic options, path independence, and stable
  dependency ordering. Actual builtin compiler/bake graphs also reuse outputs
  after unchanged, Git-HEAD-only, displayed-version-only, documentation, and
  dedicated test-only changes. A production-source edit invalidates the compiler
  and all three bake processes; reverting it restores the original cached
  outputs. Three independently invoked Debug bakes produce identical bytes.
  Concurrent fixture graphs pass with shared and separate caches while keeping
  mutable test output away from the checkout and cached inputs.
* Roc's checker passes 1,659 tests in `ReleaseSafe`; postcheck passes 622 tests
  with one skip, LIR passes 537 tests, and LIR core passes 27 tests. The migration
  exposed invalid test fixture lifetimes and allocator-dependent failure
  injection; the corrected fixtures retain leak and allocation failure checks.
* The full Roc compilation suite passes 781 tests in `ReleaseSafe`. Its new
  version-pin cache checks retain warnings when recognized human versions
  change, while keeping unpinned artifacts independent of the displayed
  version. A full-suite failure exposed a production Boxy allocation lifetime
  bug: materializing hidden dictionary arguments could grow an array after
  capturing the destination pointer. Reacquiring the index after materializing
  the arguments fixes the regression; its focused 21-test suite also passes.
* The full Roc eval module passes 69 tests without skips in `ReleaseSafe` on
  x86_64 Linux musl, using the complete LLVM 22.1.8 bundle. All 34 build steps
  pass, including linking the migrated C++ bridge and LLVM/LLD libraries.
* Actual compiler-runtime object builds pass on FreeBSD, OpenBSD, NetBSD,
  x86_64 macOS (LLVM), and aarch64 macOS in Zig 0.17 `Debug`. Equivalent Zig 0.16
  controls crash on the three BSDs and x86_64 macOS. The obsolete BSD exclusion
  is removed; macOS still deliberately uses libSystem for math symbols.

The Roc Nix development toolchain is built from hash-pinned Zig 0.17.0 source
using the locked nixpkgs LLVM 22.1.5 package. This compiler's LLVM is separate
from Roc's LLVM 22.1.8 bootstrap dependency bundle. A native-libc probe exposed
that the official prebuilt compiler selects an unusable dynamic loader inside
the Nix sandbox; patching its library source cannot change the compiler's
baked-in native detection. The source recipe applies nixpkgs' pinned `env`
probe before compilation and checks a compiled native libc executable during
installation. Its initial native-target package passed the sandbox build and
installation check, and a separate sandbox probe compiled and ran a native
libc/zlib program with Nix's compiler and linker flags intact. The subsequent
explicit-target recipe removes host-kernel detection and passes the complete
sandbox build, installation check, and native libc/zlib probe with ordinary
Nix compiler/linker flags and no explicit libc file or loader overrides.
CMake already strips its Release compiler; disabling the redundant Linux
binutils stripping pass avoids an observed ELF string-table corruption after
RPATH expansion. All checks execute without `LD_LIBRARY_PATH`.
All four supported Nix system definitions evaluate. Darwin has not received
the Linux target-pinning correction or a reproducibility validation.

The first complete native LLVM compilation took 46 minutes 24 seconds, then
failed Nix's dangling-symlink check because disabled Clang tools still installed
aliases for the absent driver. The final native recipe disables that driver
directory explicitly. The final native LLVM stage builds successfully and
passes Nix fixup; its output has only glibc/libgcc runtime references. The complete
target LLVM bundle is still building. The failed first run is
diagnostic evidence, not a successful build or performance measurement.

The first source-built host Zig also passes native and Linux/macOS/Windows
object smoke checks. A compile-time target probe then exposed another impurity:
`native` embeds the builder's running Linux kernel as its minimum and maximum
version. The final host recipe pins Linux 4.19, the locked glibc version, a
baseline CPU, and the Nix dynamic loader. A sandboxed explicit-target LLVM
static-link probe passes. This host-only correction reuses native LLVM. The
corrected host-tools stage passes its sandbox build and native GNU, pinned GNU,
Linux musl, macOS, and Windows compile/tool smoke checks. Its 11-path runtime
closure excludes native LLVM and host Zig development outputs: approximately
540 MiB of uncompressed NAR data exports to a 95 MiB file cache. The measured
export took 126.37 seconds; importing into an empty store took 3.92 seconds.
The warm host-tools build took 1.41 seconds. These are stage validation costs,
not a controlled Zig version performance comparison.

The complete x86_64 musl bundle is built. Its sandbox static libc++ probe runs
LLVM module operations and every target initializer, links all LLD drivers
and executes the ELF driver, exercises Binaryen, and compresses data with
zlib and zstd. The bundle and resulting probe have no Nix store references;
the probe has no dynamic interpreter.

The actual x86_64 release archive passes source/lock metadata, required-library,
and object architecture validation. Its 2,650 entries have normalized sorting,
timestamps, ownership, and permissions. Archive assembly `--rebuild` and a
separate saved-file comparison produce identical bytes. The locally validated
archive is from commit `4638291a35af1baf5b1d075908f2fbf2f30a37a2`; its SHA256 is
`3a5c35d79839a16e8ad053c4fd9e3f83e2f3935f1f4400a152f880e4c4ac0e21`.
This is a local validation artifact, not a published release pin or an
attestation. Assembling metadata for this integration branch reused every
compiled stage. Independent compiled-output reproduction and complete bundles
for the other seven targets remain release CI gates.

Successful build-phase durations with four-core budgets were 44m45s for native
LLVM (GCC 15.2, Release/O3), 13m02s for host Zig (ReleaseFast, stripped), 29m25s
for target LLVM (Zig C++, Release/O3), and 6m14s for Binaryen (Zig C++,
Release/O3). These are validation costs, not a controlled performance comparison.
The unchanged complete-release command took 1.93 seconds.

The initial Roc 0.16 baseline is from `ce7b298cacaee79e7dbcaba3b6cde6d8f3d73bf9`
on the same host, using four build jobs. Cold configure (`zig build --help` with
empty private Zig caches) took **64.93 seconds**. After configure, the first
`zig build roc -Doptimize=ReleaseFast -Dstrip=false` took **758.68 seconds**, with
peak RSS **19,652,156 KiB**. The unchanged warm build took **0.21 seconds**.
All 221 steps succeeded; the warm build reused compilation and still executed
the global Roc cache-clearing step. No 0.17 timing comparison is available yet.
