{
  self,
  nixpkgs,
  pkgs,
  system,
}:
let
  lib = pkgs.lib;
  targets = [
    "aarch64-linux-musl"
    "aarch64-macos-none"
    "aarch64-windows-gnu"
    "arm-linux-musleabihf"
    "x86-linux-musl"
    "x86_64-linux-musl"
    "x86_64-macos-none"
    "x86_64-windows-gnu"
  ];
  nativeTarget = if system == "aarch64-linux" then "aarch64-linux-musl" else "x86_64-linux-musl";
  versions = {
    zig = "0.17.0";
    llvm = "22.1.8";
    clang = "22.1.8";
    lld = "22.1.8";
    binaryen = "130";
    zlib = "1.3.1";
    zstd = "1.5.2";
  };

  # These retained patch records and regression fixtures are not read by the
  # library builds (LLVM_INCLUDE_TESTS/DOCS are OFF). Keep their audit changes
  # from recompiling LLVM, Zig and every downstream dependency bundle.
  ignoredInputs = [
    "llvm/ROC_PATCHES.md"
    "llvm/test"
    "llvm/unittests"
  ];
  # A source tree must contain the sibling CMake projects expected by LLVM,
  # while its store hash must not include unrelated sources or release data.
  source =
    name: paths:
    lib.cleanSourceWith {
      src = self;
      inherit name;
      filter =
        path: type:
        let
          relative = lib.removePrefix (toString self + "/") (toString path);
          selected =
            prefix:
            relative == prefix
            || lib.hasPrefix (prefix + "/") relative
            || (type == "directory" && lib.hasPrefix (relative + "/") prefix);
        in
        toString path == toString self
        || (
          lib.any selected paths
          && !(lib.any (prefix: relative == prefix || lib.hasPrefix (prefix + "/") relative) ignoredInputs)
        );
    };
  nativeLlvmSource = source "roc-bootstrap-native-llvm-source" [
    "llvm"
    "clang"
    "lld"
    "cmake"
    "third-party"
    "zig/lib/libunwind/include"
  ];
  targetLlvmSource = source "roc-bootstrap-target-llvm-source" [
    "llvm"
    "lld"
    "cmake"
    "third-party"
    "zig/lib/libunwind/include"
  ];
  zigSource = source "roc-bootstrap-zig-source" [ "zig" ];
  zlibSource = source "roc-bootstrap-zlib-source" [ "zlib" ];
  zstdSource = source "roc-bootstrap-zstd-source" [ "zstd" ];
  binaryenSource = source "roc-bootstrap-binaryen-source" [ "binaryen" ];

  # Cross builds use the bootstrapped Zig directly, never the host compiler
  # wrapper. Private caches are created by each script in its build directory.
  stage =
    {
      name,
      version,
      src,
      script,
      arguments ? [ ],
      cross ? false,
      crossCmake ? cross,
    }:
    (if cross then pkgs.stdenvNoCC else pkgs.stdenv).mkDerivation {
      pname = "roc-bootstrap-${name}";
      inherit version src;
      nativeBuildInputs = [
        pkgs.cmake
        pkgs.ninja
        pkgs.python3
      ]
      ++ lib.optionals cross [ pkgs.util-linux ];
      dontConfigure = true;
      dontInstall = true;
      dontStrip = cross;
      dontPatchELF = cross;
      strictDeps = true;
      env.CMAKE_GENERATOR = "Ninja";
      buildPhase = ''
        runHook preBuild
        export BOOTSTRAP_JOBS="$NIX_BUILD_CORES"
        if [ "$BOOTSTRAP_JOBS" -gt 4 ]; then export BOOTSTRAP_JOBS=4; fi
        ${lib.optionalString cross ''
          unset NIX_CFLAGS_COMPILE NIX_LDFLAGS
          # zig cc chooses its internal worker count from CPU affinity rather
          # than accepting build-lib's -j flag. Bound the entire stage, so its
          # CMake, Ninja and Zig workers share the same declared CPU budget.
          bootstrap_cpu_list=$(python3 -c 'import os; print(",".join(map(str, sorted(os.sched_getaffinity(0))[:int(os.environ["BOOTSTRAP_JOBS"])])))')
        ''}
        ${lib.optionalString crossCmake ''
          export BOOTSTRAP_CROSS_CMAKE=${./stages/cross-cmake.sh}
        ''}
        ${lib.optionalString cross ''taskset --cpu-list "$bootstrap_cpu_list" ''}${pkgs.runtimeShell} ${script} "$PWD" "$TMPDIR/stage-build" "$out" ${lib.escapeShellArgs arguments}
        runHook postBuild
      '';
      meta.platforms = systems;
    };
  systems = [
    "x86_64-linux"
    "aarch64-linux"
  ];
  nativeLlvm = stage {
    name = "native-llvm";
    version = versions.llvm;
    src = nativeLlvmSource;
    script = ./stages/native-llvm.sh;
  };
  hostZig =
    (stage {
      name = "host-zig";
      version = versions.zig;
      src = zigSource;
      script = ./stages/host-zig.sh;
      arguments = [
        (toString nativeLlvm)
        # Native target detection copies the builder's kernel into Zig's
        # builtin target. Pin the OS minimum and libc to avoid that input and
        # retain portability to older Linux builders and runners.
        "${pkgs.stdenv.hostPlatform.parsed.cpu.name}-linux.4.19-gnu.${pkgs.glibc.version}"
        pkgs.stdenv.cc.bintools.dynamicLinker
      ];
    }).overrideAttrs
      (_: {
        # Native ABI/linker detection probes env as an ELF binary. The sandbox has
        # no /usr/bin/env; use the pinned Nix executable, as nixpkgs' Zig package
        # does, so both the build runner and installed compiler use the Nix libc.
        postPatch = ''
          substituteInPlace zig/lib/std/zig/system.zig \
            --replace-fail '"/usr/bin/env"' '"${lib.getExe' pkgs.coreutils "env"}"'
        '';
      });
  hostTools =
    pkgs.runCommand "roc-bootstrap-host-tools-${versions.zig}"
      {
        nativeBuildInputs = [ pkgs.removeReferencesTo ];
        disallowedReferences = [ nativeLlvm ];
        meta.platforms = systems;
      }
      ''
        mkdir -p "$out/bin"
        cp ${hostZig}/bin/zig "$out/bin/zig"
        cp -r ${hostZig}/lib "$out/lib"
        for tool in llvm-ar llvm-ranlib llvm-rc llvm-tblgen; do
          cp -L ${nativeLlvm}/bin/"$tool" "$out/bin/$tool"
        done
        # The executables statically link LLVM. Build paths in diagnostic strings
        # must not retain the entire native development package in this closure.
        remove-references-to -t ${nativeLlvm} "$out/bin/"*
      '';

  forTarget =
    target:
    let
      args = [
        (toString hostTools)
        target
        "baseline"
      ];
      zlib = stage {
        name = "zlib-${target}";
        version = versions.zlib;
        src = zlibSource;
        script = ./stages/zlib.sh;
        arguments = args;
        cross = true;
      };
      zstd = stage {
        name = "zstd-${target}";
        version = versions.zstd;
        src = zstdSource;
        script = ./stages/zstd.sh;
        arguments = args;
        cross = true;
        crossCmake = false;
      };
      llvm = stage {
        name = "llvm-${target}";
        version = versions.llvm;
        src = targetLlvmSource;
        script = ./stages/target-llvm.sh;
        arguments = args ++ [
          (toString zlib)
          (toString zstd)
        ];
        cross = true;
      };
      binaryen = stage {
        name = "binaryen-${target}";
        version = versions.binaryen;
        src = binaryenSource;
        script = ./stages/binaryen.sh;
        arguments = args;
        cross = true;
      };
      metadata = pkgs.writeText "roc-deps-build-${target}.json" (
        builtins.toJSON {
          schemaVersion = 1;
          sourceRevision = self.rev or null;
          sourceDirty = !(self ? rev);
          components = versions;
          inherit target;
          cpu = "baseline";
          builderSystem = system;
          nixpkgsRevision = nixpkgs.rev;
          flakeLockSha256 = builtins.hashString "sha256" (builtins.readFile ../flake.lock);
        }
        + "\n"
      );
      deps =
        pkgs.runCommand "roc-deps-${target}-${versions.zig}"
          {
            # Only the assembled release carries provenance; it cannot force any
            # compilation to repeat when the Git revision or documentation changes.
            # Headers and static archives must work after extraction on machines
            # without Nix. Reject every store reference in the uncompressed bundle.
            allowedReferences = [ ];
          }
          ''
            mkdir -p "$out/include" "$out/lib"
            for package in ${zlib} ${zstd} ${llvm} ${binaryen}; do
              cp -r "$package/include/." "$out/include/"
              # Compiler-facing bundles contain static libraries, rather than
              # CMake/pkg-config files with absolute build and dependency prefixes.
              find "$package/lib" -maxdepth 1 -type f \( -name '*.a' -o -name '*.lib' \) \
                -exec cp '{}' "$out/lib/" \;
            done
            cp ${metadata} "$out/roc-deps-build.json"
          '';
      release =
        pkgs.runCommand "roc-deps-release-${target}-${versions.zig}"
          {
            nativeBuildInputs = [ pkgs.python3 ];
            disallowedReferences = [
              hostTools
              nativeLlvm
              hostZig
              deps
            ];
          }
          ''
            python3 ${./archive.py} --source ${deps} --output "$out" --target ${target}
            cp ${metadata} "$out/${target}.roc-deps-build.json"
          '';
    in
    {
      inherit
        zlib
        zstd
        llvm
        binaryen
        deps
        release
        ;
    };
  targetBuilds = lib.genAttrs targets forTarget;
  compilationPackages =
    lib.foldl'
      (
        result: target:
        result
        // lib.mapAttrs' (name: value: lib.nameValuePair "${name}-${target}" value) targetBuilds.${target}
      )
      {
        native-llvm = nativeLlvm;
        host-zig = hostZig;
        host-tools = hostTools;
      }
      targets;
  releaseAll = pkgs.runCommand "roc-deps-release-all-${versions.zig}" { } ''
    mkdir -p "$out"
    ${lib.concatMapStringsSep "\n" (target: ''
      cp ${targetBuilds.${target}.release}/* "$out/"
    '') targets}
    cat "$out/"*.sha256 > "$out/SHA256SUMS"
  '';
in
{
  packages = compilationPackages // {
    default = targetBuilds.${nativeTarget}.deps;
    release = releaseAll;
  };
  checks = {
    package-consumption =
      pkgs.runCommand "roc-bootstrap-package-cache-check"
        {
          nativeBuildInputs = [ pkgs.python3 ];
        }
        ''
          python3 ${../ci/test-package-consumption.py} \
            --zig ${hostTools}/bin/zig --archive-script ${./archive.py}
          touch "$out"
        '';
    archives =
      pkgs.runCommand "roc-bootstrap-archive-normalization-check"
        {
          nativeBuildInputs = [ pkgs.python3 ];
        }
        ''
          python3 ${./test-archive.py} ${./archive.py}
          touch "$out"
        '';
  };
}
