#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/dev/null
source ".venv/Scripts/activate"

cd "./srcs/backend"
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Review local secrets before starting the API."
fi

echo "FastAPI setup complete."
