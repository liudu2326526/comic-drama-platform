#!/bin/bash
# Regression test for the reusable Codex dev terminal helper.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$PROJECT_ROOT/script/dev_terminal.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/brew" <<'FAKE_BREW'
#!/bin/bash
set -euo pipefail

STATE_DIR="${TMUX_FAKE_STATE:?}"
LOG_FILE="$STATE_DIR/brew.log"
mkdir -p "$STATE_DIR"
printf '%q ' "$@" >> "$LOG_FILE"
printf '\n' >> "$LOG_FILE"

if [[ "$*" != "install tmux" ]]; then
  echo "unexpected brew command: $*" >&2
  exit 2
fi

cat > "$(dirname "$0")/tmux" <<'FAKE_TMUX'
#!/bin/bash
set -euo pipefail

STATE_DIR="${TMUX_FAKE_STATE:?}"
LOG_FILE="$STATE_DIR/tmux.log"
SESSION_FILE="$STATE_DIR/session"
mkdir -p "$STATE_DIR"
printf '%q ' "$@" >> "$LOG_FILE"
printf '\n' >> "$LOG_FILE"

case "${1:-}" in
  has-session)
    [[ -f "$SESSION_FILE" ]]
    ;;
  new-session)
    touch "$SESSION_FILE"
    ;;
  list-clients)
    if [[ "${TMUX_FAKE_CLIENTS:-0}" != "0" ]]; then
      printf 'client-1\n'
    fi
    ;;
  send-keys|attach-session|display-message)
    ;;
  *)
    echo "unexpected tmux command: $*" >&2
    exit 2
    ;;
esac
FAKE_TMUX
chmod +x "$(dirname "$0")/tmux"
FAKE_BREW
chmod +x "$TMP_DIR/brew"

assert_contains() {
  local needle="$1"
  local file="$2"
  if ! grep -Fq "$needle" "$file"; then
    echo "expected to find '$needle' in $file" >&2
    echo "--- $file ---" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_contains() {
  local needle="$1"
  local file="$2"
  if grep -Fq "$needle" "$file"; then
    echo "did not expect to find '$needle' in $file" >&2
    echo "--- $file ---" >&2
    cat "$file" >&2
    exit 1
  fi
}

export TMUX_FAKE_STATE="$TMP_DIR/state"
export PATH="$TMP_DIR:/usr/bin:/bin:/usr/sbin:/sbin"
export COMIC_DRAMA_DEV_SESSION="comic-drama-dev-test"

"$TARGET" start
assert_contains "install tmux" "$TMUX_FAKE_STATE/brew.log"
assert_contains "new-session" "$TMUX_FAKE_STATE/tmux.log"
assert_contains "script/start_all.sh" "$TMUX_FAKE_STATE/tmux.log"

: > "$TMUX_FAKE_STATE/tmux.log"
: > "$TMUX_FAKE_STATE/brew.log"
"$TARGET" start
assert_not_contains "new-session" "$TMUX_FAKE_STATE/tmux.log"
assert_not_contains "install tmux" "$TMUX_FAKE_STATE/brew.log"

"$TARGET" send "pwd"
assert_contains "send-keys" "$TMUX_FAKE_STATE/tmux.log"
assert_contains "pwd" "$TMUX_FAKE_STATE/tmux.log"

STATUS_OUTPUT="$("$TARGET" status)"
case "$STATUS_OUTPUT" in
  *"session: comic-drama-dev-test"*"$PROJECT_ROOT"*) ;;
  *)
    echo "unexpected status output:" >&2
    echo "$STATUS_OUTPUT" >&2
    exit 1
    ;;
esac

echo "dev_terminal helper test passed"
