#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/dev/null
source ".venv/Scripts/activate"

cd "./srcs/azfunc"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Azure Functions setup complete."
