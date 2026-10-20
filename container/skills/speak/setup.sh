#!/usr/bin/env bash
# One-time host setup for the speak skill: installs pinned piper-tts into
# ~/projects/.nanoclaw-tools/piper (visible to agents at /workspace/projects/...) using the agent
# image's own Python, then downloads the voices listed in voices.json.
# Usage: container/skills/speak/setup.sh
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS_ROOT="${NANOCLAW_TOOLS_DIR:-$HOME/projects/.nanoclaw-tools}"
IMAGE="${NANOCLAW_AGENT_IMAGE:-nanoclaw-agent:latest}"
HOST_DIR="$TOOLS_ROOT/piper"
CONT_DIR="/workspace/projects/.nanoclaw-tools/piper"   # same path agents use at runtime

mkdir -p "$HOST_DIR/voices"
echo "==> Installing pinned packages into $HOST_DIR/site (agent image: $IMAGE)"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$HOST_DIR:$CONT_DIR" -v "$SKILL_DIR:/skill:ro" --entrypoint sh "$IMAGE" -c \
  "pip3 install --no-cache-dir --target $CONT_DIR/site -r /skill/requirements.lock 2>&1 | tail -3"

echo "==> Downloading voices from voices.json (one-time, ~60 MB each)"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$HOST_DIR:$CONT_DIR" -v "$SKILL_DIR:/skill:ro" --entrypoint sh "$IMAGE" -c \
  "python3 /skill/scripts/speak.py --download-voices"

echo "==> Done. Agents can now run /app/skills/speak/scripts/speak \"text\""
