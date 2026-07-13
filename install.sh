#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$BASE_DIR/config.toml"

ensure_ollama() {
    if command -v ollama >/dev/null 2>&1; then
        echo "[ok] ollama found: $(ollama --version 2>/dev/null | head -1)"
        return
    fi
    echo "[!] ollama is not installed."
    read -rp "    Install it now via the official script (curl | sh)? [y/N] " ans
    case "$ans" in
        y|Y)
            curl -fsSL https://ollama.com/install.sh | sh
            ;;
        *)
            echo "    Skipping. Install manually from https://ollama.com and re-run."
            exit 1
            ;;
    esac
}

detect_vram_mb() {
    local mb

    # NVIDIA
    if command -v nvidia-smi >/dev/null 2>&1; then
        mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits \
            2>/dev/null | head -1 | tr -d '[:space:]')
        if [[ "$mb" =~ ^[0-9]+$ ]] && (( mb > 0 )); then
            echo "$mb"
            return
        fi
    fi

    local f best=0
    for f in /sys/class/drm/card*/device/mem_info_vram_total; do
        [ -r "$f" ] || continue
        mb=$(( $(<"$f") / 1048576 ))
        (( mb > best )) && best=$mb
    done
    echo "$best"
}

pick_model() {
    local vram=$1
    if   (( vram >= 16000 )); then echo "qwen3:14b"
    elif (( vram >= 10000 )); then echo "qwen3:8b"
    elif (( vram >=  6000 )); then echo "qwen3:4b"
    elif (( vram >=  4000 )); then echo "qwen3:1.7b"
    else                           echo "qwen3:0.6b"
    fi
}

set_config_model() {
    local model=$1
    local current
    current=$(grep -E '^model = ' "$CONFIG" | head -1 | sed -E 's/^model = "(.*)"/\1/')
    if [ "$current" = "$model" ]; then
        return
    fi
    sed -i -E "s|^model = \".*\"|model = \"$model\"|" "$CONFIG"
    echo "[ok] config.toml model: $current -> $model"
}

ensure_ollama

vram=$(detect_vram_mb)
if [ "$vram" -gt 0 ]; then
    echo "[ok] detected GPU VRAM: ${vram} MB"
else
    echo "[!] no NVIDIA/AMD GPU detected — falling back to the smallest model (CPU)."
fi

model="${1:-${MODEL:-$(pick_model "$vram")}}"
echo "[*] target model: $model"

if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$model"; then
    echo "[ok] $model already pulled."
else
    echo "[*] pulling $model ..."
    if ! ollama pull "$model"; then
        echo "[!] pull failed. Is the ollama server running? Try: ollama serve" >&2
        exit 1
    fi
fi

set_config_model "$model"

echo
echo "Done. Draft connection notes with:  python3 queue_agent.py --notes"
