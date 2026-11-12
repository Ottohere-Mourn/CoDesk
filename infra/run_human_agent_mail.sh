#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OSWORLD_DIR="${OSWORLD_DIR:-/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1}"
OSWORLD_PYTHON="${OSWORLD_PYTHON:-$OSWORLD_DIR/.venv/bin/python}"
SWCUB_SAFETY_ROOT="${SWCUB_SAFETY_ROOT:-/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102}"
if [[ ! -x "$OSWORLD_PYTHON" ]]; then echo "OSWorld Python not executable: $OSWORLD_PYTHON" >&2; exit 2; fi
if [[ ! -f "$SWCUB_SAFETY_ROOT/swcub/resource_safety.py" ]]; then echo "Missing resource-safety import: $SWCUB_SAFETY_ROOT/swcub/resource_safety.py" >&2; exit 2; fi
export OSWORLD_DIR
export PYTHONPATH="$REPO_ROOT:$SWCUB_SAFETY_ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"
exec "$OSWORLD_PYTHON" -m oscombo.human_agent_mail_case_runner "$@"
