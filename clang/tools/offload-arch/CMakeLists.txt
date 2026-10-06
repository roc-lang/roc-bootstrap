set(LLVM_LINK_COMPONENTS Support)

add_clang_tool(offload-arch OffloadArch.cpp NVPTXArch.cpp AMDGPUArchByKFD.cpp
               AMDGPUArchByHIP.cpp LevelZeroArch.cpp)

target_link_libraries(offload-arch PRIVATE clangBasic)
