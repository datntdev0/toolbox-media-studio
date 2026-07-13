#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=/dev/null
source ".venv/Scripts/activate"

cd "./srcs/azfunc"
func start --slient
