#!/usr/bin/env bash
# Build local_repository plugins that have a src/ directory.
# Run from any directory — the script resolves paths relative to its own location.
#
# Usage:
#   ./build_all.sh               # auto-discovers all plugins/<name>/<version>/src/
#   PLUGINS=("counter-widget/1.0.0") ./build_all.sh  # build a specific subset
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If PLUGINS is not set or empty, discover all <plugin>/<version> pairs that
# contain a src/ directory.
if [[ -z "${PLUGINS+x}" ]] || [[ ${#PLUGINS[@]} -eq 0 ]]; then
  mapfile -t PLUGINS < <(
    find "$SCRIPT_DIR" -mindepth 3 -maxdepth 3 -type d -name src \
      | sed "s|$SCRIPT_DIR/||;s|/src$||" \
      | sort
  )
fi

if [[ ${#PLUGINS[@]} -eq 0 ]]; then
  echo "⚠  No plugins found in $SCRIPT_DIR"
  exit 0
fi

echo "Building ${#PLUGINS[@]} plugin(s):"
for p in "${PLUGINS[@]}"; do echo "  • $p"; done

FAILED=()

for plugin in "${PLUGINS[@]}"; do
  src_dir="$SCRIPT_DIR/$plugin/src"
  if [[ ! -d "$src_dir" ]]; then
    echo "⚠  src/ not found for $plugin — skipping"
    continue
  fi

  echo ""
  echo "──────────────────────────────────────────────"
  echo "▶  Building $plugin"
  echo "──────────────────────────────────────────────"

  pushd "$src_dir" > /dev/null
    if npm install && npm run build; then
      echo "✅  $plugin — built successfully"
    else
      echo "❌  $plugin — build FAILED"
      FAILED+=("$plugin")
    fi
  popd > /dev/null
done

echo ""
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "✅  All plugins built successfully."
else
  echo "❌  The following plugins failed to build:"
  for f in "${FAILED[@]}"; do
    echo "   • $f"
  done
  exit 1
fi
