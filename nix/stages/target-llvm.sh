#!/bin/sh
set -eu
source_root=$1
build_dir=$2
install_prefix=$3
host_prefix=$4
target=$5
cpu=$6
zlib_prefix=$7
zstd_prefix=$8
. "${BOOTSTRAP_CROSS_CMAKE:-$(dirname -- "$0")/cross-cmake.sh}"

# The default triple controls generated code; the host triple describes where
# this LLVM library runs and selects its native target initializers. CMake's
# host detection otherwise uses the builder's architecture/OS in cross builds.
cross_cmake "$source_root/llvm" \
    -DCMAKE_PREFIX_PATH="$zlib_prefix;$zstd_prefix" \
    -DLLVM_APPEND_VC_REV=OFF \
    -DLLVM_ENABLE_BACKTRACES=OFF \
    -DLLVM_ENABLE_BINDINGS=OFF \
    -DLLVM_ENABLE_CRASH_OVERRIDES=OFF \
    -DLLVM_ENABLE_LIBEDIT=OFF \
    -DLLVM_ENABLE_LIBPFM=OFF \
    -DLLVM_ENABLE_LIBXML2=OFF \
    -DLLVM_ENABLE_OCAMLDOC=OFF \
    -DLLVM_ENABLE_PLUGINS=OFF \
    -DLLVM_ENABLE_PROJECTS=lld \
    -DLLVM_ENABLE_Z3_SOLVER=OFF \
    -DLLVM_ENABLE_ZLIB=FORCE_ON \
    -DLLVM_ENABLE_ZSTD=FORCE_ON \
    -DLLVM_USE_STATIC_ZSTD=ON \
    -DLLVM_TABLEGEN="$host_prefix/bin/llvm-tblgen" \
    -DLLVM_BUILD_UTILS=OFF \
    -DLLVM_BUILD_TOOLS=OFF \
    -DLLVM_BUILD_STATIC=ON \
    -DLLVM_INCLUDE_UTILS=OFF \
    -DLLVM_INCLUDE_TESTS=OFF \
    -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_INCLUDE_BENCHMARKS=OFF \
    -DLLVM_INCLUDE_DOCS=OFF \
    -DLLVM_PARALLEL_LINK_JOBS=1 \
    -DLLVM_PARALLEL_TABLEGEN_JOBS=2 \
    -DLLVM_HOST_TRIPLE="$target" \
    -DLLVM_DEFAULT_TARGET_TRIPLE="$target" \
    -DLLVM_TOOL_LLVM_LTO2_BUILD=OFF \
    -DLLVM_TOOL_LLVM_LTO_BUILD=OFF \
    -DLLVM_TOOL_LTO_BUILD=OFF \
    -DLLVM_TOOL_REMARKS_SHLIB_BUILD=OFF \
    -DLLD_BUILD_TOOLS=OFF
cross_install
