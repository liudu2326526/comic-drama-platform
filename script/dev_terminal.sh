#!/bin/bash
# Manage the reusable development terminal session for Codex/local startup.

set -euo pipefail

PROJECT_ROOT="${COMIC_DRAMA_PROJECT_ROOT:-/Users/macbook/Documents/trae_projects/comic-drama-platform}"
SESSION_NAME="${COMIC_DRAMA_DEV_SESSION:-comic-drama-dev}"
START_COMMAND="cd \"$PROJECT_ROOT\" && /bin/bash ./script/start_all.sh; echo; echo '[dev_terminal] session is ready. Use script/dev_terminal.sh send <command> to reuse it.'; exec \"\${SHELL:-/bin/zsh}\" -l"

usage() {
  cat <<EOF
Usage: $0 <command>

Commands:
  start           Ensure the tmux session exists and run script/start_all.sh once.
  open            Ensure the session exists and open/attach it in macOS Terminal.
  attach          Attach the current terminal to the session.
  send <command>  Send a command to the existing reusable session.
  status          Print session status.

Environment:
  COMIC_DRAMA_DEV_SESSION   Override tmux session name (default: comic-drama-dev).
  COMIC_DRAMA_PROJECT_ROOT  Override project root.
EOF
}

require_tmux() {
  if command -v tmux >/dev/null 2>&1; then
    return
  fi

  if ! command -v brew >/dev/null 2>&1; then
    echo "tmux is required and Homebrew is not available to install it." >&2
    echo "Install tmux first, then rerun: script/dev_terminal.sh start" >&2
    exit 1
  fi

  echo "tmux is not installed. Installing with Homebrew..."
  HOMEBREW_NO_AUTO_UPDATE="${HOMEBREW_NO_AUTO_UPDATE:-1}" brew install tmux
}

session_exists() {
  tmux has-session -t "$SESSION_NAME" 2>/dev/null
}

ensure_session() {
  require_tmux

  if session_exists; then
    echo "Reusing existing tmux session: $SESSION_NAME"
    return
  fi

  tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_ROOT" "$START_COMMAND"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    session_exists && break
    sleep 0.1
  done
  echo "Created tmux session: $SESSION_NAME"
}

client_count() {
  tmux list-clients -t "$SESSION_NAME" 2>/dev/null | wc -l | tr -d '[:space:]'
}

attach_command() {
  echo "tmux attach-session -t \"$SESSION_NAME\""
}

open_in_terminal() {
  ensure_session

  if [[ "$(client_count)" != "0" ]]; then
    echo "A terminal is already attached to tmux session: $SESSION_NAME"
    return
  fi

  if ! command -v osascript >/dev/null 2>&1; then
    echo "osascript is unavailable; attach manually with: tmux attach-session -t $SESSION_NAME" >&2
    exit 1
  fi

  local terminal_command
  local escaped_command
  terminal_command="cd \"$PROJECT_ROOT\" && $(attach_command)"
  escaped_command="${terminal_command//\\/\\\\}"
  escaped_command="${escaped_command//\"/\\\"}"

  osascript <<EOF
tell application "Terminal"
  activate
  do script "$escaped_command"
end tell
EOF
  echo "Opened macOS Terminal for tmux session: $SESSION_NAME"
}

send_command() {
  if [[ "$#" -eq 0 ]]; then
    echo "Missing command for send." >&2
    usage >&2
    exit 2
  fi

  ensure_session
  tmux send-keys -t "$SESSION_NAME" "$*" C-m
  echo "Sent command to tmux session $SESSION_NAME: $*"
}

print_status() {
  require_tmux

  if session_exists; then
    echo "session: $SESSION_NAME"
    echo "project: $PROJECT_ROOT"
    echo "clients: $(client_count)"
    echo "attach: $(attach_command)"
  else
    echo "session: $SESSION_NAME (not running)"
    echo "project: $PROJECT_ROOT"
    echo "start: script/dev_terminal.sh start"
  fi
}

case "${1:-start}" in
  start)
    ensure_session
    print_status
    ;;
  open)
    open_in_terminal
    ;;
  attach)
    ensure_session
    exec tmux attach-session -t "$SESSION_NAME"
    ;;
  send)
    shift
    send_command "$@"
    ;;
  status)
    print_status
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $1" >&2
    usage >&2
    exit 2
    ;;
esac
