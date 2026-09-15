#!/usr/bin/env bash
# Print the "ignores" of .markdownlint-cli2.jsonc as mdformat --exclude flags, so
# markdownlint and mdformat skip the same files from one list. Expects one
# double-quoted glob per line inside the array (see the config file).
set -euo pipefail
config="$(dirname "$0")/.markdownlint-cli2.jsonc"
sed -n '/"ignores": \[/,/^  \]/p' "$config" \
  | grep -oE '^ *"[^"]+",?$' \
  | sed -E "s/^ *\"(.*)\",?$/--exclude '\1'/" \
  | tr '\n' ' '
