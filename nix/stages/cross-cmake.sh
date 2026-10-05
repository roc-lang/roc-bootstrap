# Sourced by the target CMake stages after their explicit arguments are read.
target_os_and_abi=${target#*-}
target_os=${target_os_and_abi%-*}
case "$target_os" in
    macos*) target_os=Darwin ;;
    freebsd*) target_os=FreeBSD ;;
    netbsd*) target_os=NetBSD ;;
    openbsd*) target_os=OpenBSD ;;
    windows*) target_os=Windows ;;
    linux*) target_os=Linux ;;
    wasi*) target_os=WASI ;;
    native) target_os= ;;
esac

mkdir -p "$build_dir/zig-global-cache" "$build_dir/zig-local-cache"
export ZIG_GLOBAL_CACHE_DIR="$build_dir/zig-global-cache"
export ZIG_LOCAL_CACHE_DIR="$build_dir/zig-local-cache"
zig="$host_prefix/bin/zig"
compiler="$zig;cc;-fno-sanitize=all;-s;-target;$target;-mcpu=$cpu"
cxx_compiler="$zig;c++;-fno-sanitize=all;-s;-target;$target;-mcpu=$cpu"
prefix_map="-ffile-prefix-map=$source_root=/usr/src/roc-bootstrap -ffile-prefix-map=$build_dir=/usr/src/roc-bootstrap-build"

cross_cmake() {
    cmake_source=$1
    shift
    cmake -S "$cmake_source" -B "$build_dir" \
        -DCMAKE_INSTALL_PREFIX="$install_prefix" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_LIBDIR=lib \
        -DCMAKE_INSTALL_INCLUDEDIR=include \
        -DCMAKE_CROSSCOMPILING=True \
        -DCMAKE_SYSTEM_NAME="$target_os" \
        -DCMAKE_C_COMPILER="$compiler" \
        -DCMAKE_CXX_COMPILER="$cxx_compiler" \
        -DCMAKE_ASM_COMPILER="$compiler" \
        -DCMAKE_C_FLAGS="$prefix_map" \
        -DCMAKE_CXX_FLAGS="$prefix_map" \
        -DCMAKE_ASM_FLAGS="$prefix_map" \
        -DCMAKE_LINK_DEPENDS_USE_LINKER=OFF \
        -DCMAKE_RC_COMPILER="$host_prefix/bin/llvm-rc" \
        -DCMAKE_AR="$host_prefix/bin/llvm-ar" \
        -DCMAKE_RANLIB="$host_prefix/bin/llvm-ranlib" \
        "$@"
}

cross_install() {
    cmake --build "$build_dir" --target install --parallel "${BOOTSTRAP_JOBS:-${CMAKE_BUILD_PARALLEL_LEVEL:-2}}"
}
