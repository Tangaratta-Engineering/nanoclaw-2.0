#!/usr/bin/env bash
# One-time host setup for the inbox-triage skill: installs pinned pypdf (PDF invoice text) into
# ~/projects/.nanoclaw-tools/pdf using the agent image's own Python.
# Usage: NANOCLAW_AGENT_IMAGE=<image> container/skills/inbox-triage/setup.sh
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS_ROOT="${NANOCLAW_TOOLS_DIR:-$HOME/projects/.nanoclaw-tools}"
IMAGE="${NANOCLAW_AGENT_IMAGE:-nanoclaw-agent:latest}"
HOST_DIR="$TOOLS_ROOT/pdf"
CONT_DIR="/workspace/projects/.nanoclaw-tools/pdf"

mkdir -p "$HOST_DIR"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$HOST_DIR:$CONT_DIR" -v "$SKILL_DIR:/skill:ro" --entrypoint sh "$IMAGE" -c \
  "pip3 install --no-cache-dir --target $CONT_DIR/site -r /skill/requirements.lock 2>&1 | tail -3"
echo "==> Done: PDF text extraction available to agents."
