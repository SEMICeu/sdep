#!/usr/bin/env bash
# Public-tree gate. This repository is mirrored to a public repository where the
# private paths (export-ignore in .gitattributes), the deployment repository and
# the internal issue tracker do not exist. Nothing public may name them, so a
# reader of the mirror never meets a dead reference or internal tooling.
# Used by `make dod` and by the mirror sync before it copies anything.
set -euo pipefail
cd "$(dirname "$0")/.."

# Extended regexes, matched case-insensitively. Words that this script would
# trip over itself are spelled in two parts.
FORBIDDEN_PATTERNS=(
  # The deployment repository by name; speak about CI/CD pipelines in general terms
  "sdep-""deployment"
  # Issue and merge/pull request numbers; describe what the code does instead.
  # Three shapes, because a bare "(#n)" carries no keyword to key on: a
  # preceding noun (incl. backlog vocabulary), a preceding verb, or parentheses.
  "(issues?|MR|merge request|PR|pull request|work items?|backlog items?|tickets?|stories|story|epics?)[[:space:]]*#[0-9]+"
  "(close[sd]?|fix(e[sd])?|resolve[sd]?|refs?|see)[[:space:]]*#[0-9]+"
  "\\(#[0-9]+\\)"
  "gitlab[^ ]*/-/(issues|merge_requests)/[0-9]+"
  # The coding-assistant tooling and its instruction files are private paths;
  # "User-Agent" (HTTP header) is not a hit, hence the leading [^-].
  "cla""ude"
  "(^|[^-])\\bag""ents?\\b"
)

# CHANGELOG.md is the documented exception for issue numbers: the release trail.
ISSUE_NUMBER_EXEMPT="CHANGELOG.md"

# Binary files are skipped by grep -I, except PDFs and archives whose compressed
# streams contain no NUL byte and then trip the regexes with meaningless matches.
BINARY_EXTENSIONS='pdf|png|jpg|jpeg|gif|ico|svgz|zip|gz|tar|xlsx|docx|pptx|woff|woff2|ttf|eot'

mapfile -t files < <(scripts/public_files.sh | grep -Eiv "\.(${BINARY_EXTENSIONS})$")

found=0
for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  scan=("${files[@]}")
  case "$pattern" in
    *'#[0-9]+'*) mapfile -t scan < <(printf '%s\n' "${files[@]}" | grep -vx "$ISSUE_NUMBER_EXEMPT") ;;
  esac
  if hits=$(grep -IEni -- "$pattern" "${scan[@]}" 2>/dev/null); then
    echo "❌ Forbidden pattern \"$pattern\" in public files:"
    printf '%s\n' "$hits"
    echo ""
    found=1
  fi
done

if [ "$found" -ne 0 ]; then
  echo "Rephrase so the text stands on its own for a reader of the public mirror."
  exit 1
fi
echo "No forbidden references in $(( ${#files[@]} )) public files"
