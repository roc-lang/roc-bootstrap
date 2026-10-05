{
  description = "Reproducible Roc dependency bootstrap with Zig 0.17.0";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/64c08a7ca051951c8eae34e3e3cb1e202fe36786";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forSystems = nixpkgs.lib.genAttrs systems;
      buildFor =
        system:
        import ./nix/packages.nix {
          inherit self nixpkgs system;
          pkgs = import nixpkgs { inherit system; };
        };
    in
    {
      packages = forSystems (system: (buildFor system).packages);
      checks = forSystems (system: (buildFor system).checks);
      devShells = forSystems (system: {
        default = (import nixpkgs { inherit system; }).mkShell {
          packages = with import nixpkgs { inherit system; }; [
            cmake
            ninja
            python3
            git
            nixfmt
          ];
          shellHook = ''
            export CMAKE_GENERATOR=Ninja
            export BOOTSTRAP_JOBS="''${BOOTSTRAP_JOBS:-4}"
          '';
        };
      });
      formatter = forSystems (system: (import nixpkgs { inherit system; }).nixfmt);
    };
}
