# LLVM source and Roc patches

The LLVM, Clang, LLD, CMake, third-party, Zig, zlib, and zstd sources were
imported from the official [Zig 0.17.0 bootstrap archive](https://ziglang.org/download/0.17.0/zig-bootstrap-0.17.0.tar.xz).
Its SHA-256 is
`1e9e9b8e3c753b35dfb1d9ea48f097579fadbd3e5c1e724ab3fc5bce05477b71`.
The archive contains LLVM/Clang/LLD 22.1.8 and Zig 0.17.0. Binaryen remains
at version 130 with the existing DWARF and outlining exclusions.

The bootstrap archive already includes the generic packaging patches listed in
the repository README (including the LLVM, Clang, and LLD build/install changes
and static-only zlib). These are inherited from zig-bootstrap rather than
additional patches applied by Roc. The archive also contains its disabled SPARC
branch-relaxation change. Importing this archive does not demonstrate that any
of those changes were fixed in upstream LLVM.

Four additional Roc changes are retained because the corresponding LLVM 22.1.8
implementations still have the original whole-range searches:

* `lib/CodeGen/LiveInterval.cpp`: bound sorted live-segment/regmask searches by
  the next relevant position, preserving constant-time progress for dense data.
* `lib/CodeGen/CodeGenPrepare.cpp`: search address users and block operands in
  parallel, stopping when either establishes the first use in the current block.
  Return a head-exclusive instruction iterator on both search paths, preserving
  LLVM 22's placement of debug records before the first sunk address use.
* `lib/Transforms/Utils/InlineFunction.cpp`: split call blocks by moving the
  smaller instruction range and preserve block addresses, PHI edges, debug
  locations, and block frequencies.
* `lib/Transforms/Vectorize/SLPVectorizer.cpp`: clear and schedule only the block
  schedules touched by the current tree. LLVM 22 adds an
  `ExternalUsesWithNonUsers` reset and changes `scheduleBlock` to accept the
  vectorizer; the port preserves both changes. A failed scheduling attempt also
  registers its block so its state is cleared before the next tree.

The retained regression files are
`test/Transforms/Inline/split-smaller-call-range.ll` and
`unittests/CodeGen/LiveRangeTest.cpp`, plus the upstream
`test/DebugInfo/Generic/assignment-tracking/codegenprepare/sunk-addr.ll` debug
record regression. The Inline test exercises both split directions,
block addresses, and outgoing/self-loop PHIs. The latter exhausts disjoint
half-open ranges and sorted query sets in a small universe. The bootstrap
archive prunes the upstream test harness, so these files must be overlaid on a
full LLVM 22.1.8 source tree when running its assertion-enabled tests.

To reproduce that overlay, copy the four implementation files and the three
regression files into the same relative locations in the
[LLVM 22.1.8 source release](https://github.com/llvm/llvm-project/releases/tag/llvmorg-22.1.8).
Append `LiveRangeTest.cpp` to the `CodeGenTests` source list in
`llvm/unittests/CodeGen/CMakeLists.txt`, then configure LLVM with
`LLVM_ENABLE_ASSERTIONS=ON`, `LLVM_INCLUDE_TESTS=ON`, and at least the X86 target.
Build `opt`, `FileCheck`, and `CodeGenTests`. Run the LiveRange unit test and the
Inline, SLPVectorizer, CodeGenPrepare, and DebugInfo lit suites with that build.
