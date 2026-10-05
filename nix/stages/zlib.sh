#!/bin/sh
set -eu
source_root=$1
build_dir=$2
install_prefix=$3
host_prefix=$4
target=$5
cpu=$6
. "${BOOTSTRAP_CROSS_CMAKE:-$(dirname -- "$0")/cross-cmake.sh}"
cross_cmake "$source_root/zlib"
cross_install
