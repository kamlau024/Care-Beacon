#!/bin/bash

# Helper script to switch between production and evaluation prompts
# Usage:
#   ./switch_prompts.sh eval    # Switch to evaluation prompts
#   ./switch_prompts.sh prod    # Switch to production prompts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROMPTS_DIR="$PROJECT_ROOT/config"

PROD_PROMPTS="$PROMPTS_DIR/prompts.yaml"
EVAL_PROMPTS="$PROMPTS_DIR/prompts_eval.yaml"
BACKUP_PROMPTS="$PROMPTS_DIR/prompts.yaml.backup"

case "$1" in
  eval)
    echo "Switching to EVALUATION prompts..."
    if [ -f "$PROD_PROMPTS" ]; then
      cp "$PROD_PROMPTS" "$BACKUP_PROMPTS"
      echo "  ✓ Backed up production prompts to prompts.yaml.backup"
    fi
    cp "$EVAL_PROMPTS" "$PROMPTS_DIR/prompts_active.yaml"
    ln -sf "prompts_eval.yaml" "$PROD_PROMPTS" 2>/dev/null || cp "$EVAL_PROMPTS" "$PROD_PROMPTS"
    echo "  ✓ Switched to evaluation prompts"
    echo ""
    echo "⚠️  Remember to restart your API server for changes to take effect!"
    echo "⚠️  Run './switch_prompts.sh prod' when done to restore production prompts"
    ;;

  prod)
    echo "Switching to PRODUCTION prompts..."
    if [ -f "$BACKUP_PROMPTS" ]; then
      cp "$BACKUP_PROMPTS" "$PROD_PROMPTS"
      rm "$BACKUP_PROMPTS"
      echo "  ✓ Restored production prompts from backup"
    else
      echo "  ⚠️  No backup found, prompts may already be in production mode"
    fi
    echo "  ✓ Switched to production prompts"
    echo ""
    echo "⚠️  Remember to restart your API server for changes to take effect!"
    ;;

  *)
    echo "Usage: $0 {eval|prod}"
    echo "  eval - Switch to evaluation prompts (concise, no disclaimers)"
    echo "  prod - Switch to production prompts (comprehensive, with disclaimers)"
    exit 1
    ;;
esac
