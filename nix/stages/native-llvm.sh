#!/bin/sh
set -eu
source_root=$1
build_dir=$2
install_prefix=$3
mkdir -p "$build_dir"
cmake -S "$source_root/llvm" -B "$build_dir" \
    -DCMAKE_INSTALL_PREFIX="$install_prefix" \
    -DCMAKE_BUILD_TYPE="${BOOTSTRAP_BUILD_TYPE:-Release}" \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_C_FLAGS="-ffile-prefix-map=$source_root=/usr/src/roc-bootstrap -ffile-prefix-map=$build_dir=/usr/src/roc-bootstrap-build" \
    -DCMAKE_CXX_FLAGS="-ffile-prefix-map=$source_root=/usr/src/roc-bootstrap -ffile-prefix-map=$build_dir=/usr/src/roc-bootstrap-build" \
    -DLLVM_APPEND_VC_REV=OFF \
    -DLLVM_ENABLE_BINDINGS=OFF \
    -DLLVM_ENABLE_LIBEDIT=OFF \
    -DLLVM_ENABLE_LIBPFM=OFF \
    -DLLVM_ENABLE_LIBXML2=OFF \
    -DLLVM_ENABLE_OCAMLDOC=OFF \
    -DLLVM_ENABLE_PLUGINS=OFF \
    -DLLVM_ENABLE_PROJECTS='lld;clang' \
    -DLLVM_ENABLE_Z3_SOLVER=OFF \
    -DLLVM_ENABLE_ZLIB=OFF \
    -DLLVM_ENABLE_ZSTD=OFF \
    -DLLVM_INCLUDE_UTILS=OFF \
    -DLLVM_INCLUDE_TESTS=OFF \
    -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_INCLUDE_BENCHMARKS=OFF \
    -DLLVM_INCLUDE_DOCS=OFF \
    -DLLVM_PARALLEL_LINK_JOBS=1 \
    -DLLVM_PARALLEL_TABLEGEN_JOBS=2 \
    -DLLVM_TOOL_LLVM_LTO2_BUILD=OFF \
    -DLLVM_TOOL_LLVM_LTO_BUILD=OFF \
    -DLLVM_TOOL_LTO_BUILD=OFF \
    -DLLVM_TOOL_REMARKS_SHLIB_BUILD=OFF \
    -DCLANG_BUILD_TOOLS=OFF \
    -DCLANG_INCLUDE_DOCS=OFF \
    -DCLANG_INCLUDE_TESTS=OFF \
    -DCLANG_TOOL_CLANG_IMPORT_TEST_BUILD=OFF \
    -DCLANG_TOOL_CLANG_LINKER_WRAPPER_BUILD=OFF \
    -DCLANG_TOOL_C_INDEX_TEST_BUILD=OFF \
    -DCLANG_TOOL_LIBCLANG_BUILD=OFF
cmake --build "$build_dir" --target install --parallel "${BOOTSTRAP_JOBS:-${CMAKE_BUILD_PARALLEL_LEVEL:-2}}"
