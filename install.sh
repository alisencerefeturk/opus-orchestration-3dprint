#!/usr/bin/env bash
# Symlink this repo's skill, agent presets and statusline script into ~/.claude,
# so edits made in either place are tracked by git. Existing files are moved
# to ~/.claude/backups/opus-orchestration-<timestamp>/ first — outside skills/
# and agents/, so Claude Code doesn't load the backups as duplicates.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_DIR="$CLAUDE_DIR/backups/opus-orchestration-$STAMP"

link() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    echo "ok       $dst"
    return
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    mkdir -p "$BACKUP_DIR"
    mv "$dst" "$BACKUP_DIR/$(basename "$dst")"
    echo "backup   $dst -> $BACKUP_DIR/$(basename "$dst")"
  fi
  ln -s "$src" "$dst"
  echo "linked   $dst -> $src"
}

link "$REPO/skills/opus-orchestration" "$CLAUDE_DIR/skills/opus-orchestration"
link "$REPO/skills/3d-print-workflow"  "$CLAUDE_DIR/skills/3d-print-workflow"
link "$REPO/agents/sonnet-worker.md"   "$CLAUDE_DIR/agents/sonnet-worker.md"
link "$REPO/agents/haiku-worker.md"    "$CLAUDE_DIR/agents/haiku-worker.md"
link "$REPO/statusline/statusline.sh"  "$CLAUDE_DIR/statusline.sh"
chmod +x "$REPO/statusline/statusline.sh"

cat <<'EOF'

Done. If you haven't already, add this to ~/.claude/settings.json:

  "statusLine": { "type": "command", "command": "~/.claude/statusline.sh" }
EOF
