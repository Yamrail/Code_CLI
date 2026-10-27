#!/bin/sh
set -eu
yr_script_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -x "$yr_script_root/.venv/bin/python" ]; then
  exec "$yr_script_root/.venv/bin/python" -B "$yr_script_root/yr_code.py" "$@"
fi
exec python3 -B "$yr_script_root/yr_code.py" "$@"
