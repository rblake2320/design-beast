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
# Generated assets can contain private source images, prompts, voices, and job
# metadata. Keep every file created by setup or the service owner-only.
umask 077
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
  "judge_model": "qwen3-vl:8b",
  "expand_models": "qwen3.6:27b,gemma3:latest"
}
JSON
  echo "wrote beast.config.json (Linux defaults; UE features auto-disabled)"
fi

echo "== [4/7] ollama judge + expander models =="
command -v ollama >/dev/null || { echo "ollama missing — install it first"; exit 1; }
ollama pull qwen3-vl:8b
ollama pull qwen3.6:27b
ollama pull gemma3:latest

echo "== [5/7] kokoro voice models =="
cd ~/beast/models/kokoro
if [ ! -f kokoro-v1.0.onnx ] || [ "$(stat -c %s kokoro-v1.0.onnx)" -lt 300000000 ]; then
  curl -fL --retry 5 --retry-all-errors -o kokoro-v1.0.onnx.part \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
  [ "$(stat -c %s kokoro-v1.0.onnx.part)" -ge 300000000 ]
  mv -f kokoro-v1.0.onnx.part kokoro-v1.0.onnx
fi
if ! "$VENV_DIR/bin/python" -c 'import sys,zipfile; sys.exit(0 if zipfile.is_zipfile("voices-v1.0.bin") else 1)'; then
  curl -fL --retry 5 --retry-all-errors -o voices-v1.0.bin.part \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
  "$VENV_DIR/bin/python" -c 'import zipfile; p="voices-v1.0.bin.part"; assert zipfile.is_zipfile(p); z=zipfile.ZipFile(p); assert z.testzip() is None'
  mv -f voices-v1.0.bin.part voices-v1.0.bin
fi
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
trap 'docker logout nvcr.io >/dev/null 2>&1 || true' EXIT
for pair in "nim-flux:8018:nvcr.io/nim/black-forest-labs/flux.1-schnell@sha256:6edcdd428fd524dde76090f3a0797ae76e0b593d5445702e2eaf9bc20c375042" \
            "nim-kontext:8019:nvcr.io/nim/black-forest-labs/flux.1-kontext-dev@sha256:5cf4854fde49b0646a6807fcc616b8b54afc38f9936db442a98e6cba3c72f6e8"; do
  name="${pair%%:*}"; rest="${pair#*:}"; port="${rest%%:*}"; img="${rest#*:}"
  docker image inspect "$img" >/dev/null 2>&1 || docker pull "$img"
  docker container inspect "$name" >/dev/null 2>&1 || docker create --name "$name" \
    --restart unless-stopped --gpus all --ipc=host --shm-size=8g \
    -e NGC_API_KEY="$NGC_API_KEY" -e HF_TOKEN="$HF_TOKEN" \
    -p "127.0.0.1:$port":8000 -v ~/beast/nim-cache:/opt/nim/.cache/ "$img"
  docker update --restart unless-stopped "$name" >/dev/null
done

# TRELLIS is deliberately on-demand: its image-capable profile cannot share a
# 128 GB Spark with the always-warm FLUX NIMs. Beast stops the image NIMs before
# starting it, and stops TRELLIS before bringing an image NIM back.
trellis_img="nvcr.io/nim/microsoft/trellis@sha256:fe31904b816a1e1a91764a82e65b33908ab6643bb234d1807be5bf31d22b10b7"
trellis_profile="c4ac2b36251be5c1cc3e6792ede219646c2c6dd83b18682d7521c318db8630a8" # large:image
docker image inspect "$trellis_img" >/dev/null 2>&1 || docker pull "$trellis_img"
docker container inspect nim-trellis >/dev/null 2>&1 || docker create --name nim-trellis \
  --restart no --gpus all --ipc=host --shm-size=8g \
  -e NGC_API_KEY="$NGC_API_KEY" -e HF_TOKEN="$HF_TOKEN" \
  -e NIM_MODEL_PROFILE="$trellis_profile" \
  -p 127.0.0.1:8017:8000 -v ~/beast/nim-cache:/opt/nim/.cache/ "$trellis_img"
docker update --restart no nim-trellis >/dev/null

# Official Wan2.2 A14B I2V NVFP4 NIM for Spark-native fast animation.
# It is a heavy, synchronous backend, so it stays off until Beast acquires the
# exclusive GPU lease and swaps out FLUX/Kontext/TRELLIS.
wan_img="nvcr.io/nim/wan-ai/wan2.2@sha256:05c1d390af4eec607b654172fa889ae8cef2b2c238e84516514e61e5ba52e63b"
wan_profile="6804489a9416df56fbc1e64b16ca12c356b225349134a5e4282446da4fc024f2" # i2v:nvfp4
docker image inspect "$wan_img" >/dev/null 2>&1 || docker pull "$wan_img"
docker container inspect nim-wan >/dev/null 2>&1 || docker create --name nim-wan \
  --restart no --device nvidia.com/gpu=all --shm-size=16g \
  -e NGC_API_KEY="$NGC_API_KEY" -e HF_TOKEN="$HF_TOKEN" \
  -e NIM_MODEL_VARIANT=i2v -e NIM_MODEL_PRECISION=nvfp4 \
  -e NIM_MODEL_PROFILE="$wan_profile" -e NIM_TRITON_REQUEST_TIMEOUT=900000000 \
  -p 127.0.0.1:8021:8000 -v ~/beast/nim-cache:/opt/nim/.cache/ "$wan_img"
docker update --restart no nim-wan >/dev/null
docker logout nvcr.io >/dev/null
trap - EXIT
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
UMask=0077
WorkingDirectory=$ROOT
EnvironmentFile=-$CREDS_FILE
ExecStartPre=/usr/bin/chmod -R go-rwx $ROOT
ExecStart=$VENV_DIR/bin/python studio/server.py
Restart=always
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=default.target
EOF
# Harden an existing checkout too: earlier releases used the host's permissive
# 0002 umask, leaving jobs.db and generated artifacts readable by local users.
# Removing only group/other bits preserves executable flags and owner access.
chmod -R go-rwx "$ROOT"
systemctl --user daemon-reload
systemctl --user enable --now beast-studio.service
if command -v loginctl >/dev/null && [ "$(loginctl show-user "$USER" -p Linger --value)" != "yes" ]; then
  sudo loginctl enable-linger "$USER"
fi
echo "service enabled; health: curl -s localhost:8787/api/health"
