#!/bin/sh

set -eu

TZ_VALUE="${TZ:-${TIMEZONE:-Asia/Shanghai}}"
export TZ="$TZ_VALUE"
export TIMEZONE="$TZ_VALUE"
CONFIG_PATH="${CONFIG_FILE:-/app/config.json}"
DEFAULT_CONFIG_PATH="${CONFIG_DEFAULT_FILE:-/app/config.default.json}"

if [ -f "/usr/share/zoneinfo/$TZ_VALUE" ]; then
  ln -snf "/usr/share/zoneinfo/$TZ_VALUE" /etc/localtime
  echo "$TZ_VALUE" > /etc/timezone
fi

config_dir="$(dirname "$CONFIG_PATH")"
mkdir -p "$config_dir"
if [ ! -f "$CONFIG_PATH" ]; then
  if [ -f "$DEFAULT_CONFIG_PATH" ]; then
    cp "$DEFAULT_CONFIG_PATH" "$CONFIG_PATH"
  else
    printf '{}\n' > "$CONFIG_PATH"
  fi
fi
export CONFIG_FILE="$CONFIG_PATH"

role="${1:-app}"
if [ "$#" -gt 0 ]; then
  shift
fi

start_app() {
  nginx
  exec uvicorn src.api.main:app --host "${FASTAPI_HOST:-0.0.0.0}" --port "${FASTAPI_PORT:-8000}" "$@"
}

start_worker() {
  exec python -m src.collectors_v2.worker_main "$@"
}

case "$role" in
  app)
    start_app "$@"
    ;;
  worker)
    start_worker "$@"
    ;;
  *)
    exec "$role" "$@"
    ;;
esac
