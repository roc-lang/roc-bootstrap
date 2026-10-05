#!/bin/sh
set -eu
source_root=$1
build_dir=$2
install_prefix=$3
llvm_prefix=$4
mkdir -p "$build_dir/zig-global-cache" "$build_dir/zig-local-cache"
export ZIG_GLOBAL_CACHE_DIR="$build_dir/zig-global-cache"
export ZIG_LOCAL_CACHE_DIR="$build_dir/zig-local-cache"
cmake -S "$source_root/zig" -B "$build_dir" \
    -DCMAKE_INSTALL_PREFIX="$install_prefix" \
    -DCMAKE_PREFIX_PATH="$llvm_prefix" \
    -DCMAKE_BUILD_TYPE="${BOOTSTRAP_BUILD_TYPE:-Release}" \
    -DCMAKE_C_FLAGS="-ffile-prefix-map=$source_root=/usr/src/roc-bootstrap -ffile-prefix-map=$build_dir=/usr/src/roc-bootstrap-build" \
    -DCMAKE_CXX_FLAGS="-ffile-prefix-map=$source_root=/usr/src/roc-bootstrap -ffile-prefix-map=$build_dir=/usr/src/roc-bootstrap-build" \
    -DZIG_VERSION=0.17.0 \
    -DZIG_RELEASE_SAFE=OFF \
    -DZIG_TARGET_MCPU=baseline \
    -DZIG_EXTRA_BUILD_ARGS="-j${BOOTSTRAP_JOBS:-${CMAKE_BUILD_PARALLEL_LEVEL:-2}};-Dno-langref=true"
cmake --build "$build_dir" --target install --parallel "${BOOTSTRAP_JOBS:-${CMAKE_BUILD_PARALLEL_LEVEL:-2}}"
