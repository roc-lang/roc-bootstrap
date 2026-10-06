#!/bin/sh
set -eu
source_root=$1
build_dir=$2
install_prefix=$3
host_prefix=$4
target=$5
cpu=$6
. "${BOOTSTRAP_CROSS_CMAKE:-$(dirname -- "$0")/cross-cmake.sh}"
cross_cmake "$source_root/binaryen" \
    -DCMAKE_C_FLAGS="$prefix_map -g0" \
    -DCMAKE_CXX_FLAGS="$prefix_map -g0" \
    -DCMAKE_ASM_FLAGS="$prefix_map -g0" \
    -DBUILD_TOOLS=OFF \
    -DBUILD_TESTS=OFF \
    -DBUILD_FUZZTEST=OFF \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_LLVM_DWARF=OFF \
    -DBUILD_MIMALLOC=OFF \
    -DINSTALL_LIBS=ON
cross_install
