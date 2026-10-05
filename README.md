# roc-bootstrap

The purpose of this project is to start with minimum system dependencies and
end with a fully operational Roc compiler for any target.

Fundamentally, this project is a fork of the great work from [zig-bootstrap](https://github.com/ziglang/zig-bootstrap).
Now that Roc is written in Zig, we have an equivalent core dependency tree.

Eventually, this project will be used for cross compiling Roc releases to all supported targets.
For now, this project is planned as a way to stage all of Roc's dependencies for easy download.
This will make is so with the download of a single archive, anyone can start building Roc.
On top of that, this is any easy place to host llvm builds for download.

Until Roc has a verioned released, this repo will not vendor and build Roc.
It will just vendor and build the deps for compiling Roc.

## Version Information

This repository copies sources from upstream. Patches listed below. Use git
to find and inspect the patch diffs.

 * LLVM, LLD, Clang 22.1.8
 * Binaryen 130
 * zlib 1.3.1
 * zstd 1.5.2
 * Zig 0.17.0

For other versions, check the git tags of this repository.

### Patches

The Zig 0.17.0 bootstrap archive already carries the generic LLVM, Clang, LLD,
and zlib packaging changes below. Roc retains four additional LLVM scaling
patches and the Binaryen exclusions. Their upstream status and import checksum
are recorded in [llvm/ROC_PATCHES.md](llvm/ROC_PATCHES.md).

 * all: Deleted unused files.
 * LLVM: Skip sorted regmask positions outside live segments.
 * LLVM: Bound address insertion-point searches by both the block and use list.
 * LLVM: Clear and schedule only blocks touched by the current SLP tree.
 * LLVM: Move the smaller call-site instruction range when splitting for inlining.
 * LLVM: Support .lib extension for static zstd.
 * LLVM: Don't pass -static when building executables.
 * LLVM: OpenBSD `llvm-config` logic
 * Clang: Ignore the examples directory
 * Clang: Disable building of libclang-cpp.so.
 * Clang: remove `nvptx-arch` and `amdgpu-arch` symlinks
 * Clang: remove broken scan-build manpage install logic
 * LLD: Added additional include directory to Zig's libunwind.
 * LLD: Respect `LLD_BUILD_TOOLS=OFF`
 * LLD: Skip building docs
 * LLD: OpenBSD `findMajMinShlib()` logic
 * Binaryen: Disable LLVM DWARF support.
 * Binaryen: Disable the outlining pass and its LLVM suffix-tree dependency.
 * zlib: Delete the ability to build a shared library.

## Host System Dependencies

 * C++17 compiler capable of building LLVM, Clang, and LLD from source (GCC 8+
   or Clang 10+; the build uses `-ffile-prefix-map` for reproducible paths)
     * On some systems, static libstdc++/libc++ may need to be installed
 * CMake 3.20 or later
 * make, ninja, or any other build system supported by CMake
 * POSIX system (bash, mkdir, cd)
 * Python 3

## Build Instructions

```
./build <arch>-<os>-<abi> <mcpu>
```

All parameters are required:

 * `<arch>-<os>-<abi>`: Replace with one of the Supported Targets below, or use
   `native` for the `<arch>` value (e.g. `native-linux-gnu`) to use the native
   architecture.
 * `<mcpu>`: Replace with a `-mcpu` parameter of Zig. `baseline` is recommended
   and means it will target a generic CPU for the target. `native` means it
   will target the native CPU. See the Zig documentation for more details.

Please be aware of the following two CMake environment variables that can
significantly affect how long it takes to build:

 * `CMAKE_GENERATOR` can be used to select a different generator instead of the
   default. For example, `CMAKE_GENERATOR=Ninja`.
 * `BOOTSTRAP_JOBS` sets the stage build concurrency. If unset, stages use
   `CMAKE_BUILD_PARALLEL_LEVEL`, then default to two jobs. This applies to Ninja
   as well as Make. The Nix development shell defaults to four jobs; Nix package
   builds use at most four jobs and restrict target-stage CPU affinity.

When it succeeds, the dependency bundle is in `out/<target>-<cpu>/`.

### Reproducible Nix builds

The flake pins the build tools and builds without network access inside the
Nix sandbox. Linux builders on `x86_64-linux` and `aarch64-linux` can build all
eight release targets:

```sh
nix build .#release-x86_64-linux-musl
nix build .#deps-aarch64-macos-none
nix develop
```

`release-<target>` produces a normalized archive with `include/`, `lib/`, and
`roc-deps-build.json` at its root. The target appears in the filename and
metadata. This layout supports Zig 0.17's hashed package cache, including
standalone fetch followed by a consumer build. `deps-<target>` exposes its
`include/` and `lib/` directly. The default
package is the builder architecture's Linux musl dependency bundle. `release`
builds all eight archives. Each bundle includes `roc-deps-build.json` describing
its source revision, component versions, target, baseline CPU, builder, and
flake lock. CI releases require a clean committed source tree.

Native LLVM, host Zig, zlib, zstd, target LLVM/LLD, and Binaryen are separate
derivations. Edits to documentation and release metadata reuse compiled stages;
Binaryen edits reuse LLVM and host Zig. Each stage has a private writable Zig
cache, and the default compile concurrency is bounded. The `host-tools` package
contains the installed tools and Zig library tree needed for cross compilation.

The [release workflow](.github/workflows/release-roc-deps.yml) transfers the
complete host-tools runtime closure to target jobs, validates all eight bundles,
checks an x86_64 Linux rebuild, and signs SLSA build-provenance attestations.
It creates a draft only after those checks pass. See
[the upgrade validation record](docs/zig-0.17-upgrade.md) for the local checks
and release sequence, including provenance verification.

Routine builds and CI use the locked Nix inputs and content hashes. Roc verifies
its pinned Zig package hashes when fetching dependency bundles. Attestation API
checks run only during release publication or an explicitly requested provenance
audit; local builds and cache checks do not require a GitHub token.

## Windows Build Instructions

Bootstrapping on Windows with MSVC is also possible via `build.bat`, which
takes the same arguments as `build` above.

This script requires that the "C++ CMake tools for Windows" component be
installed via the Visual Studio installer.

The script must be run within the `Developer Command Prompt for VS 2019` shell:

```
build.bat <arch>-<os>-<abi> <mcpu>
```

To build for x86 Windows, run the script within the `x86 Native Tools Command Prompt for VS 2019`.

### Supported Targets

> Note: Roc does not support as many targets as Zig.
So this list is probably overly zealous in terms of support. Though theoretically, roc should run on anything zig can compile it to.

If you try a "not tested" one and find a problem please file an issue,
and a pull request linking to the issue in the table.

If you try a "not tested" one and find that it works, please file a pull request
changing the status to "OK".

If you try an "OK" one and it does not work, please check if there is an existing
issue, and if not, file an issue.

Note: Generally, for Linux targets, we prefer the musl libc builds over the
glibc builds here, because musl builds end up producing a static binary, which
is more portable across Linux distributions.

#### FreeBSD

| Target                     | Status |
|----------------------------|--------|
| `aarch64-freebsd-none`     | OK     |
| `arm-freebsd-eabihf`       | OK     |
| `powerpc64-freebsd-none`   | OK     |
| `powerpc64le-freebsd-none` | OK     |
| `riscv64-freebsd-none`     | OK     |
| `x86_64-freebsd-none`      | OK     |

#### Linux

| Target                      | Status |
|-----------------------------|--------|
| `aarch64-linux-gnu`         | OK     |
| `aarch64-linux-musl`        | OK     |
| `aarch64_be-linux-gnu`      | OK     |
| `aarch64_be-linux-musl`     | OK     |
| `arm-linux-gnueabi`         | OK     |
| `arm-linux-gnueabihf`       | OK     |
| `arm-linux-musleabi`        | OK     |
| `arm-linux-musleabihf`      | OK     |
| `armeb-linux-gnueabi`       | OK     |
| `armeb-linux-gnueabihf`     | OK     |
| `armeb-linux-musleabi`      | OK     |
| `armeb-linux-musleabihf`    | OK     |
| `hexagon-linux-musl`        | [#215](https://codeberg.org/ziglang/zig-bootstrap/issues/215) |
| `loongarch64-linux-gnu`     | OK     |
| `loongarch64-linux-gnusf`   | OK     |
| `loongarch64-linux-musl`    | OK     |
| `loongarch64-linux-muslsf`  | OK     |
| `mips-linux-gnueabi`        | OK     |
| `mips-linux-gnueabihf`      | OK     |
| `mips-linux-musleabi`       | OK     |
| `mips-linux-musleabihf`     | OK     |
| `mips64-linux-gnuabi64`     | OK     |
| `mips64-linux-gnuabin32`    | OK     |
| `mips64-linux-muslabi64`    | OK     |
| `mips64-linux-muslabin32`   | OK     |
| `mips64el-linux-gnuabi64`   | OK     |
| `mips64el-linux-gnuabin32`  | [#214](https://codeberg.org/ziglang/zig-bootstrap/issues/214) |
| `mips64el-linux-muslabi64`  | OK     |
| `mips64el-linux-muslabin32` | OK     |
| `mipsel-linux-gnueabi`      | OK     |
| `mipsel-linux-gnueabihf`    | OK     |
| `mipsel-linux-musleabi`     | OK     |
| `mipsel-linux-musleabihf`   | OK     |
| `powerpc-linux-gnueabi`     | OK     |
| `powerpc-linux-gnueabihf`   | OK     |
| `powerpc-linux-musleabi`    | OK     |
| `powerpc-linux-musleabihf`  | OK     |
| `powerpc64-linux-musl`      | OK     |
| `powerpc64le-linux-gnu`     | OK     |
| `powerpc64le-linux-musl`    | OK     |
| `riscv32-linux-gnu`         | OK     |
| `riscv32-linux-musl`        | OK     |
| `riscv64-linux-gnu`         | OK     |
| `riscv64-linux-musl`        | OK     |
| `s390x-linux-gnu`           | OK     |
| `s390x-linux-musl`          | OK     |
| `sparc-linux-gnu`           | [#117](https://codeberg.org/ziglang/zig-bootstrap/issues/117) |
| `sparc64-linux-gnu`         | [#172](https://codeberg.org/ziglang/zig-bootstrap/issues/172) |
| `thumb-linux-musleabi`      | OK     |
| `thumb-linux-musleabihf`    | OK     |
| `thumbeb-linux-musleabi`    | OK     |
| `thumbeb-linux-musleabihf`  | OK     |
| `x86-linux-gnu`             | OK     |
| `x86-linux-musl`            | OK     |
| `x86_64-linux-gnu`          | OK     |
| `x86_64-linux-gnux32`       | OK     |
| `x86_64-linux-musl`         | OK     |
| `x86_64-linux-muslx32`      | OK     |

#### macOS

| Target               | Status |
|----------------------|--------|
| `aarch64-macos-none` | OK     |
| `x86_64-macos-none`  | OK     |

#### NetBSD

| Target                   | Status |
|--------------------------|--------|
| `aarch64-netbsd-none`    | OK     |
| `aarch64_be-netbsd-none` | OK     |
| `arm-netbsd-eabi`        | OK     |
| `arm-netbsd-eabihf`      | OK     |
| `armeb-netbsd-eabi`      | OK     |
| `armeb-netbsd-eabihf`    | OK     |
| `mips-netbsd-eabi`       | OK     |
| `mips-netbsd-eabihf`     | OK     |
| `mipsel-netbsd-eabi`     | OK     |
| `mipsel-netbsd-eabihf`   | OK     |
| `powerpc-netbsd-eabi`    | OK     |
| `powerpc-netbsd-eabihf`  | OK     |
| `riscv32-netbsd-none`    | [#233](https://codeberg.org/ziglang/zig-bootstrap/issues/233) |
| `riscv64-netbsd-none`    | [#234](https://codeberg.org/ziglang/zig-bootstrap/issues/234) |
| `sparc-netbsd-none`      | [#230](https://codeberg.org/ziglang/zig-bootstrap/issues/230) |
| `sparc64-netbsd-none`    | [#231](https://codeberg.org/ziglang/zig-bootstrap/issues/231) |
| `x86-netbsd-none`        | OK     |
| `x86_64-netbsd-none`     | OK     |

#### OpenBSD

| Target                    | Status |
|---------------------------|--------|
| `aarch64-openbsd-none`    | OK     |
| `arm-openbsd-eabi`        | OK     |
| `mips64-openbsd-none`     | OK     |
| `mips64el-openbsd-none`   | OK     |
| `powerpc-openbsd-eabihf`  | OK     |
| `powerpc64-openbsd-none`  | OK     |
| `riscv64-openbsd-none`    | OK     |
| `sparc64-openbsd-none`    | [#251](https://codeberg.org/ziglang/zig-bootstrap/issues/251) |
| `x86-openbsd-none`        | OK     |
| `x86_64-openbsd-none`     | OK     |

#### Windows

| Target                | Status |
|-----------------------|--------|
| `aarch64-windows-gnu` | OK     |
| `thumb-windows-gnu`   | OK     |
| `x86-windows-gnu`     | OK     |
| `x86_64-windows-gnu`  | OK     |

### LLVM scaling regression tests

The regression inputs for the local scaling patches are retained under
`llvm/test/Transforms/Inline/` and `llvm/unittests/CodeGen/LiveRangeTest.cpp`.
To test them with LLVM's upstream harness, use the complete LLVM 22.1.8 source
release: copy the patched `InlineFunction.cpp`, `SLPVectorizer.cpp`,
`CodeGenPrepare.cpp`, and `LiveInterval.cpp` into their corresponding source
paths, copy the regression inputs, and add `LiveRangeTest.cpp` to the
`CodeGenTests` sources in `llvm/unittests/CodeGen/CMakeLists.txt`.

Build with assertions enabled and the X86 target, then run `CodeGenTests`,
`IRTests`, `UtilsTests`, and `VectorizeTests`, plus `llvm-lit` over
`Transforms/Inline`, `Transforms/SLPVectorizer`, `Transforms/CodeGenPrepare`,
and `DebugInfo/Generic`. The live-range test exhaustively compares sorted slot
queries against direct segment membership, including empty inputs and holes.
The inlining test checks both split directions, block addresses, and self-loop
and successor PHI edges with LLVM's verifier.
