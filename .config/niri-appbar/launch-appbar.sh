#!/usr/bin/env sh

set -eu

runtime_dir="${XDG_RUNTIME_DIR:-/tmp}"
launcher_pidfile="$runtime_dir/niri-appbar-launcher.pid"
launcher_lockfile="$runtime_dir/niri-appbar-launcher.lock"
appbar_log="$runtime_dir/niri-appbar.log"

: >"$appbar_log"

exec 9>"$launcher_lockfile"
if ! flock -n 9; then
    old_pid="$(cat "$launcher_pidfile" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && [ "$old_pid" != "$$" ] && kill -0 "$old_pid" 2>/dev/null; then
        kill "$old_pid" 2>/dev/null || true
        sleep 0.3
        kill -0 "$old_pid" 2>/dev/null && kill -9 "$old_pid" 2>/dev/null || true
    fi
    flock -w 3 9 || exit 0
fi

printf '%s\n' "$$" >"$launcher_pidfile"

child_pid=""
cleanup() {
    if [ "$(cat "$launcher_pidfile" 2>/dev/null || true)" = "$$" ]; then
        rm -f "$launcher_pidfile"
    fi
}
stop() {
    [ -n "$child_pid" ] && kill "$child_pid" 2>/dev/null || true
    cleanup
    exit 0
}
trap stop INT TERM
trap cleanup EXIT

while :; do
    "/home/vladelaina/.config/niri-appbar/appbar.py" >>"$appbar_log" 2>&1 &
    child_pid="$!"
    if wait "$child_pid"; then
        status=0
    else
        status="$?"
    fi
    child_pid=""
    printf '%s appbar exited with status %s; restarting\n' "$(date '+%F %T')" "$status" >>"$appbar_log"
    sleep 1
done
