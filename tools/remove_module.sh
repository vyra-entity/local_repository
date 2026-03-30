#!/usr/bin/env bash
# remove_module.sh
# ---------------------------------------------------------------------------
# Removes a module (optionally a specific version) from the local repository.
# Deletes the module's directory and rebuilds index.json via update_index.sh.
#
# Usage:
#   cd /path/to/local_repository
#   ./tools/remove_module.sh <module_name> [<version>]
#
#   <module_name>  Name of the module to remove (e.g. testmodul)
#   <version>      Optional. If given, removes only that version directory.
#                  If omitted, removes ALL versions and the module directory.
#
# Examples:
#   ./tools/remove_module.sh testmodul           # remove all versions
#   ./tools/remove_module.sh testmodul 0.1.0     # remove only version 0.1.0
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODULES_DIR="$REPO_ROOT/modules"
UPDATE_INDEX="$SCRIPT_DIR/update_index.sh"

MODULE_NAME="${1:-}"
VERSION="${2:-}"

# ── Validate arguments ────────────────────────────────────────────────────────
if [[ -z "$MODULE_NAME" ]]; then
  echo "Usage: $0 <module_name> [<version>]" >&2
  exit 1
fi

MODULE_DIR="$MODULES_DIR/$MODULE_NAME"

if [[ ! -d "$MODULE_DIR" ]]; then
  echo "❌  Module directory not found: $MODULE_DIR" >&2
  exit 1
fi

# ── Remove version or entire module ──────────────────────────────────────────
if [[ -n "$VERSION" ]]; then
  VERSION_DIR="$MODULE_DIR/$VERSION"
  if [[ ! -d "$VERSION_DIR" ]]; then
    echo "❌  Version directory not found: $VERSION_DIR" >&2
    exit 1
  fi
  echo "🗑️   Removing module '$MODULE_NAME' version '$VERSION' ..."
  rm -rf "$VERSION_DIR"
  echo "✅  Removed: $VERSION_DIR"

  # If no versions remain, remove the module directory entirely
  if [[ -z "$(ls -A "$MODULE_DIR" 2>/dev/null)" ]]; then
    rm -rf "$MODULE_DIR"
    echo "✅  Module directory empty — removed: $MODULE_DIR"
  fi
else
  echo "🗑️   Removing module '$MODULE_NAME' (all versions) ..."
  rm -rf "$MODULE_DIR"
  echo "✅  Removed: $MODULE_DIR"
fi

# ── Rebuild index.json ────────────────────────────────────────────────────────
echo "🔄  Rebuilding index.json ..."
cd "$REPO_ROOT"
bash "$UPDATE_INDEX"
echo "✅  index.json updated."
