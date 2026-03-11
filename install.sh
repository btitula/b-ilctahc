#!/usr/bin/env zsh
# ──────────────────────────────────────────────────────────────────────────────
# install.sh — ChatGPT CLI setup
# Usage: zsh install.sh
# ──────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_PATH="$HOME/.local/bin/cgpt"
CONFIG_DIR="$HOME/.config/chatgpt-cli"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ChatGPT CLI Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Check Python ───────────────────────────────────────────────────────────
echo "→ Checking Python..."
PYTHON=$(command -v python3 || command -v python)
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: Python not found. Activate your conda env first:"
  echo "   conda activate <your-env>"
  exit 1
fi
PY_VER=$($PYTHON --version 2>&1)
echo "  OK: $PY_VER at $PYTHON"

# ── 2. Install dependencies ───────────────────────────────────────────────────
echo ""
echo "→ Installing Python dependencies..."
$PYTHON -m pip install --quiet --upgrade openai anthropic typer rich pyyaml
echo "  OK: openai anthropic typer rich pyyaml installed"

# ── 3. Copy script to ~/.local/bin ────────────────────────────────────────────
echo ""
echo "→ Installing cgpt to $INSTALL_PATH ..."
mkdir -p "$HOME/.local/bin"
cp "$SCRIPT_DIR/cgpt.py" "$INSTALL_PATH"
# sed -i "1s|.*|#!${PYTHON}|" "$INSTALL_PATH"   # patch shebang to current python
sed -i '' "1s|.*|#!${PYTHON}|" "$INSTALL_PATH"

chmod +x "$INSTALL_PATH"
echo "  OK: Installed: $INSTALL_PATH"

# ── 4. Init config + projects ─────────────────────────────────────────────────
echo ""
echo "→ Initialising config..."
$PYTHON "$INSTALL_PATH" --init
echo ""

# ── 4b. Copy custom project files from repo ───────────────────────────────────
if [[ -d "$SCRIPT_DIR/projects" ]]; then
  echo "→ Copying project files..."
  mkdir -p "$CONFIG_DIR/projects"
  cp "$SCRIPT_DIR/projects/"*.yaml "$CONFIG_DIR/projects/"
  COUNT=$(ls "$SCRIPT_DIR/projects/"*.yaml 2>/dev/null | wc -l | tr -d ' ')
  echo "  OK: $COUNT projects copied to $CONFIG_DIR/projects/"
  echo ""
fi

# ── 5. Zsh alias ──────────────────────────────────────────────────────────────
ZSHRC="$HOME/.zshrc"
ALIAS_MARKER="# chatgpt-cli alias"

if grep -q "$ALIAS_MARKER" "$ZSHRC" 2>/dev/null; then
  echo "→ Zsh alias already present in $ZSHRC — skipping."
else
  echo ""
  echo "→ Adding alias to $ZSHRC ..."
  cat >> "$ZSHRC" <<EOF

${ALIAS_MARKER}
alias ??="${INSTALL_PATH}"
alias ??p="${INSTALL_PATH} --list"
alias ??h="${INSTALL_PATH} --history"
alias ??c="${INSTALL_PATH} --clear"
EOF
  echo "  OK: Aliases added"
fi

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Installation complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  1. Set your API key:"
echo "     nano $CONFIG_DIR/config.yaml"
echo ""
echo "  2. Reload your shell:"
echo "     source ~/.zshrc"
echo ""
echo "  3. Try it:"
echo "     ?? what is the difference between CMD and ENTRYPOINT"
echo "     ?? devops how do I force a new ECS deployment"
echo "     ?? python write a boto3 s3 bucket lister"
echo ""
echo "  Shortcuts:"
echo "     ??p           → list all projects"
echo "     ??h           → show history (current project)"
echo "     ??c           → clear history (current project)"
echo "     ?? -p devops  → explicit project flag"
echo "     ?? -n devops  → new conversation (ignore history this turn)"
echo ""
