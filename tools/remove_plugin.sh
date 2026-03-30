#!/usr/bin/env bash
# remove_plugin.sh
# ---------------------------------------------------------------------------
# Removes a plugin (optionally a specific version) from the local repository.
# Deletes the plugin's directory and rebuilds index.json via update_index.sh.
#
# Usage:
#   cd /path/to/local_repository
#   ./tools/remove_plugin.sh <plugin_name> [<version>]
#
#   <plugin_name>  Name of the plugin to remove (e.g. counter-widget)
#   <version>      Optional. If given, removes only that version directory.
#                  If omitted, removes ALL versions and the plugin directory.
#
# Examples:
#   ./tools/remove_plugin.sh counter-widget           # remove all versions
#   ./tools/remove_plugin.sh counter-widget 1.0.0     # remove only version 1.0.0
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGINS_DIR="$REPO_ROOT/plugins"
UPDATE_INDEX="$SCRIPT_DIR/update_index.sh"

PLUGIN_NAME="${1:-}"
VERSION="${2:-}"

# ── Validate arguments ────────────────────────────────────────────────────────
if [[ -z "$PLUGIN_NAME" ]]; then
  echo "Usage: $0 <plugin_name> [<version>]" >&2
  exit 1
fi

PLUGIN_DIR="$PLUGINS_DIR/$PLUGIN_NAME"

if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "❌  Plugin directory not found: $PLUGIN_DIR" >&2
  exit 1
fi

# ── Remove version or entire plugin ──────────────────────────────────────────
if [[ -n "$VERSION" ]]; then
  VERSION_DIR="$PLUGIN_DIR/$VERSION"
  if [[ ! -d "$VERSION_DIR" ]]; then
    echo "❌  Version directory not found: $VERSION_DIR" >&2
    exit 1
  fi
  echo "🗑️   Removing plugin '$PLUGIN_NAME' version '$VERSION' ..."
  rm -rf "$VERSION_DIR"
  echo "✅  Removed: $VERSION_DIR"

  # If no versions remain, remove the plugin directory entirely
  if [[ -z "$(ls -A "$PLUGIN_DIR" 2>/dev/null)" ]]; then
    rm -rf "$PLUGIN_DIR"
    echo "✅  Plugin directory empty — removed: $PLUGIN_DIR"
  fi
else
  echo "🗑️   Removing plugin '$PLUGIN_NAME' (all versions) ..."
  rm -rf "$PLUGIN_DIR"
  echo "✅  Removed: $PLUGIN_DIR"
fi

# ── Rebuild index.json ────────────────────────────────────────────────────────
echo "🔄  Rebuilding index.json ..."
cd "$REPO_ROOT"
bash "$UPDATE_INDEX"
echo "✅  index.json updated."
