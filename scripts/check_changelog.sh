#!/bin/bash
# Changelog currency (make dod): code changed since the commit that last touched
# CHANGELOG.md should come with a changelog change in the working tree. A miss
# is a warning, not a failure (see warn in run-dod.sh): not every change needs
# an entry. Documentation-only and generated files are out of scope.
set -uo pipefail

SCOPE=(backend/app backend/alembic backend/pyproject.toml keycloak postgres test-data scripts tests Makefile docker-compose.yml)

last=$(git log -1 --format=%H -- CHANGELOG.md)
changed=$(
  {
    git diff --name-only "$last" HEAD -- "${SCOPE[@]}"
    git status --porcelain -- "${SCOPE[@]}" | cut -c4- | sed 's/.* -> //'
  } | sort -u
)

if [ -z "$changed" ]; then
  echo "No code changes since the last CHANGELOG.md commit (${last:0:8})"
  exit 0
fi
if ! git diff --quiet -- CHANGELOG.md; then
  echo "CHANGELOG.md is modified in the working tree, covering:"
  echo "$changed" | sed 's/^/  /'
  exit 0
fi
echo "Code changed since the last CHANGELOG.md commit (${last:0:8}) without a changelog change:"
echo "$changed" | sed 's/^/  /'
echo "Add the change to CHANGELOG.md, or ignore this if it needs no entry"
exit 1
