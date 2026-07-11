#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/dev/null
source ".venv/Scripts/activate"

cd "./srcs/api"
uvicorn app.main:app --reload --port 8000
