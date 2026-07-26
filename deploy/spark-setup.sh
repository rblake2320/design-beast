#!/usr/bin/env bash
# Beast Studio — DGX Spark / Linux arm64 node setup (phase A: control plane + image gen)
#
#   git clone https://github.com/rblake2320/design-beast.git ~/design-beast
#   cd ~/design-beast && NGC_API_KEY=... HF_TOKEN=... bash deploy/spark-setup.sh
#
# Idempotent. Heavy pulls run in the foreground — use tmux/nohup for the big ones.
# Phase A gives you: server + judge + expand + FLUX image generation + TTS.
# Phase B (optional, later): ComfyUI + Wan/LTX video, TRELLIS 3D.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
VENV_DIR="${BEAST_VENV:-$ROOT/.venv}"
CREDS_FILE="${BEAST_CREDS_FILE:-$HOME/beast/creds.env}"

echo "== [1/7] python deps =="
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
"$VENV_DIR/bin/python" -m pip install --quiet -r requirements.txt

echo "== [2/7] imagemagick (grade step) =="
if command -v magick >/dev/null || command -v convert >/dev/null; then
  echo "ImageMagick present"
else
  echo "ImageMagick absent — Pillow fallback remains fully functional"
fi

echo "== [3/7] node config =="
if [ ! -f beast.config.json ]; then
  mkdir -p ~/beast/models/kokoro ~/beast/nim-cache
  cat > beast.config.json <<'JSON'
{
  "comfy_dir": "~/beast/comfyui",
  "kokoro_dir": "~/beast/models/kokoro",
  "esrgan": "",
  "blender": "/usr/bin/blender",
  "judge_model": "qwen3-vl:8b"
}
JSON
  echo "wrote beast.config.json (Linux defaults; UE features auto-disabled)"
fi

echo "== [4/7] ollama judge + expander models =="
command -v ollama >/dev/null || { echo "ollama missing — install it first"; exit 1; }
ollama pull qwen3-vl:8b
ollama list | grep -q "qwen3.6:27b\|gemma3" || ollama pull gemma3:latest

echo "== [5/7] kokoro voice models =="
cd ~/beast/models/kokoro
[ -f kokoro-v1.0.onnx ] || curl -L -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
[ -f voices-v1.0.bin ] || curl -L -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd - >/dev/null

echo "== [6/7] NIM containers (arm64 — verified multi-arch) =="
if [ -f "$CREDS_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CREDS_FILE"
fi
: "${NGC_API_KEY:?set NGC_API_KEY or provide $CREDS_FILE}"
: "${HF_TOKEN:?set HF_TOKEN or provide $CREDS_FILE}"
mkdir -p "$HOME/beast/nim-cache"
chmod 700 "$HOME/beast"
chmod 600 "$CREDS_FILE" 2>/dev/null || true
echo "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin
for pair in "nim-flux:8018:nvcr.io/nim/black-forest-labs/flux.1-schnell@sha256:6edcdd428fd524dde76090f3a0797ae76e0b593d5445702e2eaf9bc20c375042" \
            "nim-kontext:8019:nvcr.io/nim/black-forest-labs/flux.1-kontext-dev:latest"; do
  name="${pair%%:*}"; rest="${pair#*:}"; port="${rest%%:*}"; img="${rest#*:}"
  docker image inspect "$img" >/dev/null 2>&1 || docker pull "$img"
  docker container inspect "$name" >/dev/null 2>&1 || docker create --name "$name" \
    --restart unless-stopped --gpus all --ipc=host --shm-size=8g \
    -e NGC_API_KEY="$NGC_API_KEY" -e HF_TOKEN="$HF_TOKEN" \
    -p "$port":8000 -v ~/beast/nim-cache:/opt/nim/.cache/ "$img"
  docker update --restart unless-stopped "$name" >/dev/null
done
echo "created (not started) — start from the Studio Backends panel or: docker start nim-flux"

echo "== [7/7] durable user service =="
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/beast-studio.service" <<EOF
[Unit]
Description=Beast Studio local AI production API
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$ROOT
EnvironmentFile=-$CREDS_FILE
ExecStart=$VENV_DIR/bin/python studio/server.py
Restart=always
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now beast-studio.service
if command -v loginctl >/dev/null && [ "$(loginctl show-user "$USER" -p Linger --value)" != "yes" ]; then
  sudo loginctl enable-linger "$USER"
fi
echo "service enabled; health: curl -s localhost:8787/api/health"
