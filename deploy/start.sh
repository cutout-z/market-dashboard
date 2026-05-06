#!/usr/bin/env bash
# Start market dashboard + autoresearch worker.
# API keys are loaded into the environment by systemd via EnvironmentFile,
# then inherited by docker compose and passed to the containers.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

cd "$PROJECT_DIR"
exec docker compose up --remove-orphans
