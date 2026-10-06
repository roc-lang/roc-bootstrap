#!/usr/bin/env python3
"""Write reviewable release notes from the CI build identity."""

import os
import re
import sys

if len(sys.argv) != 3:
    sys.exit("usage: release-notes.py <tag> <source-commit>")
tag, revision = sys.argv[1:]
if tag != "zig-0.17.0" or not re.fullmatch(r"[0-9a-f]{40}", revision):
    sys.exit("tag or source revision does not match this release configuration")
repository = os.environ["GITHUB_REPOSITORY"]
run_id = os.environ["GITHUB_RUN_ID"]
print(f"""Dependencies for Zig 0.17.0: LLVM/Clang/LLD 22.1.8, Binaryen 130,
zlib 1.3.1, and zstd 1.5.2. Every target uses the baseline CPU.

Built from [{revision}](https://github.com/{repository}/commit/{revision}) in
[GitHub Actions](https://github.com/{repository}/actions/runs/{run_id}) using the
pinned Nix flake. Each archive includes `roc-deps-build.json` with its source,
toolchain, target, and lock identity. `SHA256SUMS` records the archive digests.
The x86_64 Linux job also checks a rebuild for reproducibility; build and closure
transfer measurements are attached to the workflow run.

Routine builds use locked Nix inputs and Roc's pinned Zig package content
hashes; they do not require the GitHub attestation API. To check downloaded
archive bytes against the release manifest:

```sh
sha256sum --check --ignore-missing SHA256SUMS
```

All eight archives must pass SLSA build-provenance verification before this draft
is created. For an explicit release provenance audit:

```sh
gh attestation verify x86_64-linux-musl.tar.xz \\
  --repo {repository} \\
  --signer-workflow {repository}/.github/workflows/release-roc-deps.yml \\
  --source-ref refs/tags/{tag} --source-digest {revision} \\
  --deny-self-hosted-runners
```

Publish this draft before updating Roc's dependency URLs and Zig package hashes.
""")
