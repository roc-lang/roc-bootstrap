# Additional cross-target validation

Local checks on 2026-10-05 used Zig 0.17.0 and LLVM 22.1.8 from the cached
source-built host tools. ARM64 Windows was selected to exercise MinGW, COFF,
Windows CMake detection, and a different CPU architecture from the completed
Linux build. These checks found a cross-target configuration error before a
complete Windows library build.

The original ARM64 Windows recipe correctly set `LLVM_DEFAULT_TARGET_TRIPLE`
but generated `LLVM_HOST_TRIPLE=x86_64-w64-windows-gnu` and
`LLVM_NATIVE_ARCH=X86`. LLVM's MinGW host detection uses the builder's processor;
other cross configurations can use the builder's `config.guess` result. The
default triple describes generated code, while the host triple describes where
the LLVM library runs and selects its native initialization functions.

Commit `c928024de4c299ce230c95491a83aa0d5b0a8882` explicitly sets
`LLVM_HOST_TRIPLE` to the requested target in `nix/stages/target-llvm.sh`.
Configure-only derivations used the exact target-stage options with that fix
and asserted the actual generated `llvm-config.h` values:

| Requested target | Host and default triples | Native architecture | Native initializer |
| --- | --- | --- | --- |
| `aarch64-windows-gnu` | `aarch64-windows-gnu` | `AArch64` | `LLVMInitializeAArch64Target` |
| `x86_64-linux-musl` | `x86_64-linux-musl` | `X86` | `LLVMInitializeX86Target` |

Both configurations passed with CMake `Release` (`-O3 -DNDEBUG`), two cores,
and one Nix job. Their maximum sampled daemon-tree RSS was 393,924 KiB. Binaryen
and zlib do not reconstruct LLVM host triples; zstd passes its target directly
to Zig. Binaryen's limited processor-specific flags did not demonstrate a
similar failure, so those stages were left unchanged.

The ordinary Nix zlib and zstd stages completed for ARM64 Windows:

```sh
nix build --offline --no-update-lock-file --cores 4 --max-jobs 1 \
  .#zlib-aarch64-windows-gnu .#zstd-aarch64-windows-gnu
```

The resulting `libz.a` (109,586 bytes) and `zstd.lib` (582,346 bytes) each passed
the release validator's first-object ARM64 COFF check. The maximum sampled
daemon-tree RSS was 509,248 KiB. LLVM CMake also found both libraries through
the declared dependency prefixes.

A subsequent Windows compile check completed the `LLVMSupport` target
(183/183 Ninja steps) using the corrected configuration and two cores.
`lldCommon` and even its individual Ninja object rules pull linked LLVM
libraries through order dependencies. That later phase was intentionally
stopped to free the local CPU budget for complete corrected Linux builds; no
compiler error had appeared. Its maximum sampled daemon-tree RSS was
663,652 KiB. This establishes a Support compilation result, not a completed
LLD build, published smoke artifact, or native Windows execution result.

Exact commands, private Nix overrides, generated-header assertions, logs, and
five-second RSS samples are retained under
`/tmp/roc-017-aarch64-windows-i3c8mje8/`. The result records are
`compression-validation.json`, `llvm-configure-validation.json`, and
`llvm-bounded-validation.json`. Shell syntax and whitespace checks passed for
the recipe change.

Complete corrected bundles and full local Roc checks remain separate gates.
The additional [eight-target hosted validation run](https://github.com/roc-lang/roc-bootstrap/actions/runs/37299463411)
was dispatched at `a4c0cd54b` with an independent Linux rebuild; publication
and attestation were disabled. Its results are not claimed here as completed
local validation.
