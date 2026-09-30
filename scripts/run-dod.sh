#!/bin/bash
# Definition of Done runner, the automated half of the DoD (`make dod`); the
# manual review items live in the developer tooling, outside the public tree.
# dod = `make all` + API snapshots/diff + docs checks, see the dod target in the Makefile.
#
# Every step runs with its full output in tmp/dod/<step>.log; the terminal gets
# one line per step. On failure the tail of that step's log is shown and the run
# stops, so a session or pipeline never has to read the whole output.
#
# Order: cheap and content-only steps first, the stack-bound suites last, so a
# failure that needs a docs or allowlist fix costs seconds, not the full cycle.
#
# Markers: tmp/dod/failed holds the failed step's name, tmp/dod/passed the time
# of the last full pass. `make dod-continue` (DOD_CONTINUE=1) reruns the cheap
# steps unconditionally and resumes the stack-bound chain from the failed step;
# it refuses when a backend/ file changed after the failure, because that
# invalidates the backend test and the image scan that already passed.
set -uo pipefail

LOG_DIR="tmp/dod"
TAIL_LINES="${DOD_TAIL_LINES:-40}"
RESUME_FROM=""
SKIPPED=""
RESUMABLE_STEPS="backend-test test-cve-offline test-cve up keycloak-configure test-migrations
  test-full-1 test-full-keep-1 test-full-keep-2 test-full-2
  test-perf-1 test-perf-keep-1 test-perf-keep-2 test-perf-2 test-malware"
mkdir -p "$LOG_DIR"

if [ "${DOD_CONTINUE:-}" = 1 ]; then
  if [ ! -f "$LOG_DIR/failed" ]; then
    echo "❌ Nothing to continue: no failed step recorded in $LOG_DIR/failed. Run make dod."
    exit 1
  fi
  RESUME_FROM=$(cat "$LOG_DIR/failed")
  rm -f "$LOG_DIR/passed"
  # Only the stack-bound chain (run_all) is resumable; a cheap step reruns anyway.
  case " $RESUMABLE_STEPS " in
    *" $RESUME_FROM "*) ;;
    *) echo "ℹ️  Failed step '$RESUME_FROM' is a cheap step, running everything."; RESUME_FROM="" ;;
  esac
  CHANGED=$(git ls-files -m -o --exclude-standard -- backend | while read -r f; do
    [ -e "$f" ] && [ "$f" -nt "$LOG_DIR/failed" ] && echo "$f"; done)
  if [ -n "$CHANGED" ]; then
    echo "❌ Cannot continue: backend/ changed after the failure, the passed backend test and image scan are stale. Run make dod."
    echo "$CHANGED" | sed 's/^/   /'
    exit 1
  fi
else
  rm -f "$LOG_DIR"/*.log "$LOG_DIR"/failed "$LOG_DIR"/passed
fi

FAILED=""
START_ALL=$(date +%s)

# step: a failing check stops the run. warn: same output, but the run goes on
# (for checks that need a human judgement, such as changelog currency).
step() {
  local name="$1"; shift
  local log="$LOG_DIR/$name.log"
  local start
  # Resuming: skip the stack-bound steps that passed before the failed one. The stack
  # start and Keycloak provisioning are idempotent and always run: the stack may have
  # been stopped since the failure.
  if [ -n "$RESUME_FROM" ] && [ "${RESUMABLE:-}" = 1 ]; then
    if [ "$name" = "$RESUME_FROM" ]; then
      RESUME_FROM=""
    elif [ "$name" != up ] && [ "$name" != keycloak-configure ]; then
      printf "▶ %-24s⏭  passed in the previous run, not rerun\n" "$name"
      SKIPPED="$SKIPPED $name"
      return 0
    fi
  fi
  start=$(date +%s)
  printf "▶ %-24s" "$name"
  if "$@" >"$log" 2>&1; then
    printf "✅ %4ss\n" "$(( $(date +%s) - start ))"
    return 0
  fi
  if [ "${STEP_MODE:-fail}" = warn ]; then
    printf "⚠️  %4ss  (see %s)\n" "$(( $(date +%s) - start ))" "$log"
  else
    printf "❌ %4ss  (see %s)\n" "$(( $(date +%s) - start ))" "$log"
  fi
  echo "─── last $TAIL_LINES lines of $log ───"
  tail -n "$TAIL_LINES" "$log"
  echo "───"
  [ "${STEP_MODE:-fail}" = warn ] && return 0
  FAILED="$name"
  return 1
}
warn() { STEP_MODE=warn step "$@"; }

# ── Static checks (no services needed) ─────────────────────────────────
snapshot_review() {
  # Regenerated snapshots accept any contract change: list what changed for review.
  git --no-pager diff --stat -- backend/tests/api/fixtures docs/API_DIFF_TECH.md
  echo "Review the diff above: every change must be an intended contract change"
}

run_docs_checks() {
  step forbidden-references ./scripts/check_forbidden_references.sh || return 1
  step md-validate-links make --no-print-directory md-validate-links || return 1
  step architecture-tree python3 scripts/check_architecture_tree.py || return 1
  step docs-consistency bash -c 'cd backend && API_MODE=internal uv run python ../scripts/check_docs_consistency.py' || return 1
  warn changelog ./scripts/check_changelog.sh
}

run_api() {
  step api-snapshot-update make -C backend --no-print-directory api-snapshot-update || return 1
  step api-diff-update make -C backend --no-print-directory api-diff-update || return 1
  step snapshot-review snapshot_review || return 1
}

# Markdown after the API step, which regenerates docs/API_DIFF_TECH.md.
run_markdown() {
  step md-format make --no-print-directory md-format || return 1
  step md-lint make --no-print-directory md-lint || return 1
}

# Same order as `make all`: backend test and image scan (Docker only), then the stack
# is started and Keycloak provisioned for the suites that need it. Resumable.
run_all() {
  RESUMABLE=1
  step backend-test make -C backend --no-print-directory test || return 1
  step test-cve-offline make --no-print-directory test-cve-offline || return 1
  step test-cve make --no-print-directory test-cve || return 1
  step up make --no-print-directory up || return 1
  step keycloak-configure make --no-print-directory keycloak-configure || return 1
  step test-migrations make --no-print-directory test-migrations || return 1
  step test-full-1 make --no-print-directory test-full || return 1
  step test-full-keep-1 make --no-print-directory test-full-keep || return 1
  step test-full-keep-2 make --no-print-directory test-full-keep || return 1
  step test-full-2 make --no-print-directory test-full || return 1
  step test-perf-1 make --no-print-directory test-perf PERF_AUTO_CONFIRM=true || return 1
  step test-perf-keep-1 make --no-print-directory test-perf-keep PERF_AUTO_CONFIRM=true || return 1
  step test-perf-keep-2 make --no-print-directory test-perf-keep PERF_AUTO_CONFIRM=true || return 1
  step test-perf-2 make --no-print-directory test-perf PERF_AUTO_CONFIRM=true || return 1
  step test-malware make --no-print-directory test-malware || return 1
}

if [ -n "$RESUME_FROM" ]; then
  echo "🧪 Definition of Done, continued from step '$RESUME_FROM' (cheap steps rerun, passed stack-bound steps skipped; all logs go in $LOG_DIR/)"
else
  echo "🧪 Definition of Done (incl. clean-keep-keep-clean test-cycle for full and perf; all logs go in $LOG_DIR/)"
fi
echo ""
run_docs_checks && run_api && run_markdown && run_all
echo ""
if [ -n "$FAILED" ]; then
  echo "$FAILED" > "$LOG_DIR/failed"
  echo "❌ Definition of Done failed at step '$FAILED' after $(( $(date +%s) - START_ALL ))s"
  echo "   Fix the cause (log tail above, full log in $LOG_DIR/$FAILED.log), then rerun make dod,"
  echo "   or make dod-continue to rerun the cheap steps and resume the stack-bound chain from '$FAILED'."
  echo "   Or run the DoD checklist in the developer tooling: it reads that log, fixes the cause, and reruns."
  exit 1
fi
rm -f "$LOG_DIR/failed"
date -Is > "$LOG_DIR/passed"
echo "✅ Definition of Done passed in $(( $(date +%s) - START_ALL ))s"
[ -n "$SKIPPED" ] && echo "   Not rerun (passed in the previous run):$SKIPPED"
echo "   Manual review remains (see the DoD checklist in the developer tooling)"
