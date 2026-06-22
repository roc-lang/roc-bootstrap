FILE(GLOB support_HEADERS *.h)
set(support_SOURCES
  archive.cpp
  bits.cpp
  colors.cpp
  command-line.cpp
  debug.cpp
  dfa_minimization.cpp
  file.cpp
  int128.cpp
  intervals.cpp
  istring.cpp
  json.cpp
  name.cpp
  path.cpp
  safe_integer.cpp
  string.cpp
  threads.cpp
  utilities.cpp
  ${support_HEADERS}
)

# Roc omits the outlining pass, which is the only user of these suffix-tree
# sources. They depend on LLVM support headers, and Roc's compiler already links
# its own LLVM.
target_sources(binaryen PRIVATE ${support_SOURCES})
