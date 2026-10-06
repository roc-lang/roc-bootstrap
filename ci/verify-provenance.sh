#!/usr/bin/env bash
# Release publication / explicit audit only. Routine builds use content hashes.
set -euo pipefail

if [[ $# != 3 ]]; then
    echo "usage: $0 <archive> <tag> <source-commit>" >&2
    exit 2
fi
archive=$1
tag=$2
revision=$3
policy=(--repo roc-lang/roc-bootstrap
    --signer-workflow roc-lang/roc-bootstrap/.github/workflows/release-roc-deps.yml
    --source-ref "refs/tags/$tag" --source-digest "$revision"
    --deny-self-hosted-runners)

gh attestation verify "$archive" "${policy[@]}"

# Exercise the policy as well as its successful path. A release attestation
# alone must not pass the default SLSA build-provenance predicate.
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
cp "$archive" "$temporary/modified"
printf '\001' >> "$temporary/modified"
if gh attestation verify "$temporary/modified" "${policy[@]}"; then
    echo "modified artifact unexpectedly passed provenance verification" >&2
    exit 1
fi
if gh attestation verify "$archive" "${policy[@]}" --source-ref "refs/tags/$tag-invalid"; then
    echo "wrong tag unexpectedly passed provenance verification" >&2
    exit 1
fi
wrong_revision=0000000000000000000000000000000000000000
if [[ $revision == "$wrong_revision" ]]; then
    wrong_revision=1111111111111111111111111111111111111111
fi
if gh attestation verify "$archive" "${policy[@]}" --source-digest "$wrong_revision"; then
    echo "wrong source commit unexpectedly passed provenance verification" >&2
    exit 1
fi
