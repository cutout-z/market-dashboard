#!/usr/bin/env bash
# ARCHIVED VPS STARTER ONLY.
#
# Active runtime moved to the QNAP NAS runner on 2026-05-29. Use
# tools/nas-runner/compose.yml and tools/nas-runner/scripts/nas-job instead.
#
# Start market dashboard + autoresearch worker.
# API keys are loaded into the environment by systemd via EnvironmentFile,
# then inherited by docker compose and passed to the containers.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

cd "$PROJECT_DIR"
exec docker compose up --remove-orphans
