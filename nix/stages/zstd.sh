#!/bin/sh
set -eu
source_root=$1
build_dir=$2
install_prefix=$3
host_prefix=$4
target=$5
cpu=$6
mkdir -p "$build_dir/zig-global-cache" "$build_dir/zig-local-cache" "$install_prefix/include" "$install_prefix/lib"
export ZIG_GLOBAL_CACHE_DIR="$build_dir/zig-global-cache"
export ZIG_LOCAL_CACHE_DIR="$build_dir/zig-local-cache"
cp "$source_root/zstd/lib/zstd.h" "$source_root/zstd/lib/zstd_errors.h" "$install_prefix/include/"
case "$target" in
    *-windows-*) library_name=zstd.lib ;;
    *) library_name=libzstd.a ;;
esac
cd "$build_dir"
"$host_prefix/bin/zig" build-lib \
  --name zstd \
  -target "$target" \
  -mcpu="$cpu" \
  -fno-sanitize-c -fstrip -OReleaseFast \
  -femit-bin="$install_prefix/lib/$library_name" \
  -lc \
  -cflags \
  -ffile-prefix-map="$source_root=/usr/src/roc-bootstrap" \
  -ffile-prefix-map="$build_dir=/usr/src/roc-bootstrap-build" -- \
  "$source_root/zstd/lib/decompress/zstd_ddict.c" \
  "$source_root/zstd/lib/decompress/zstd_decompress.c" \
  "$source_root/zstd/lib/decompress/huf_decompress.c" \
  "$source_root/zstd/lib/decompress/huf_decompress_amd64.S" \
  "$source_root/zstd/lib/decompress/zstd_decompress_block.c" \
  "$source_root/zstd/lib/compress/zstdmt_compress.c" \
  "$source_root/zstd/lib/compress/zstd_opt.c" \
  "$source_root/zstd/lib/compress/hist.c" \
  "$source_root/zstd/lib/compress/zstd_ldm.c" \
  "$source_root/zstd/lib/compress/zstd_fast.c" \
  "$source_root/zstd/lib/compress/zstd_compress_literals.c" \
  "$source_root/zstd/lib/compress/zstd_double_fast.c" \
  "$source_root/zstd/lib/compress/huf_compress.c" \
  "$source_root/zstd/lib/compress/fse_compress.c" \
  "$source_root/zstd/lib/compress/zstd_lazy.c" \
  "$source_root/zstd/lib/compress/zstd_compress.c" \
  "$source_root/zstd/lib/compress/zstd_compress_sequences.c" \
  "$source_root/zstd/lib/compress/zstd_compress_superblock.c" \
  "$source_root/zstd/lib/deprecated/zbuff_compress.c" \
  "$source_root/zstd/lib/deprecated/zbuff_decompress.c" \
  "$source_root/zstd/lib/deprecated/zbuff_common.c" \
  "$source_root/zstd/lib/common/entropy_common.c" \
  "$source_root/zstd/lib/common/pool.c" \
  "$source_root/zstd/lib/common/threading.c" \
  "$source_root/zstd/lib/common/zstd_common.c" \
  "$source_root/zstd/lib/common/xxhash.c" \
  "$source_root/zstd/lib/common/debug.c" \
  "$source_root/zstd/lib/common/fse_decompress.c" \
  "$source_root/zstd/lib/common/error_private.c" \
  "$source_root/zstd/lib/dictBuilder/zdict.c" \
  "$source_root/zstd/lib/dictBuilder/divsufsort.c" \
  "$source_root/zstd/lib/dictBuilder/fastcover.c" \
  "$source_root/zstd/lib/dictBuilder/cover.c"
