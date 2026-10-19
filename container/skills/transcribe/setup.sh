#!/usr/bin/env bash
# One-time host setup for the transcribe skill: installs pinned faster-whisper into
# ~/projects/.nanoclaw-tools/whisper (visible to agents at /workspace/projects/...) using the
# agent image's own Python (so binary wheels match), then downloads a Whisper model.
# Usage: container/skills/transcribe/setup.sh [model ...]   (tiny|base|small|medium; default: base small)
set -euo pipefail

MODELS=("$@")
[ ${#MODELS[@]} -eq 0 ] && MODELS=(base small)
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS_ROOT="${NANOCLAW_TOOLS_DIR:-$HOME/projects/.nanoclaw-tools}"
IMAGE="${NANOCLAW_AGENT_IMAGE:-nanoclaw-agent:latest}"
HOST_DIR="$TOOLS_ROOT/whisper"
CONT_DIR="/workspace/projects/.nanoclaw-tools/whisper"   # same path agents use at runtime

mkdir -p "$HOST_DIR/models"
echo "==> Installing pinned packages into $HOST_DIR/site (agent image: $IMAGE)"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$HOST_DIR:$CONT_DIR" -v "$SKILL_DIR:/skill:ro" --entrypoint sh "$IMAGE" -c \
  "pip3 install --no-cache-dir --target $CONT_DIR/site -r /skill/requirements.lock 2>&1 | tail -3"

for MODEL in "${MODELS[@]}"; do
  echo "==> Downloading model '$MODEL' (one-time)"
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$HOST_DIR:$CONT_DIR" -v "$SKILL_DIR:/skill:ro" --entrypoint sh "$IMAGE" -c \
    "python3 /skill/scripts/transcribe.py --download-only --model $MODEL"
done

echo "==> Done. Agents can now run /app/skills/transcribe/scripts/transcribe <audio file>"
