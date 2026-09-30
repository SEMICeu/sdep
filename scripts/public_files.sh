#!/usr/bin/env bash
# Print the public files of this repository, one per line: tracked or
# untracked-but-not-ignored, minus the private paths marked `export-ignore`
# in .gitattributes (the files a public mirror never receives).
# Optional pathspecs narrow the list, e.g. `scripts/public_files.sh '*.md'`.
set -euo pipefail
cd "$(dirname "$0")/.."
git ls-files --cached --others --exclude-standard -- "$@" \
  | git check-attr --stdin export-ignore \
  | awk -F': ' '$3 != "set" { print $1 }'
