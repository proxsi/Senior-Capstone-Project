#!/bin/bash
# Legacy Linux entrypoint using the original virtual environment path.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
set -e

PROJECT_ROOT="/home/devbox/project"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT"
export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-8080}"
export API_RELOAD="false"

exec "$PROJECT_ROOT/bin/python" -m api_server.server
