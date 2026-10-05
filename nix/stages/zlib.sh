#!/bin/sh
set -eu
source_root=$1
build_dir=$2
install_prefix=$3
host_prefix=$4
target=$5
cpu=$6
. "${BOOTSTRAP_CROSS_CMAKE:-$(dirname -- "$0")/cross-cmake.sh}"
# zlib's CMake configuration renames zconf.h in its source directory. Give
# this stage a private source copy so ./build also leaves the checkout intact.
mkdir -p "$build_dir/source"
cp -R "$source_root/zlib/." "$build_dir/source/"
cross_cmake "$build_dir/source" -DZLIB_BUILD_EXAMPLES=OFF
cross_install
