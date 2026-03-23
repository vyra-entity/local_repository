#!/usr/bin/env bash
# Build all local_repository plugins that have a src/ directory.
# Run from any directory — the script resolves paths relative to its own location.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PLUGINS=(
  "counter-widget/1.0.0"
  "module-count-widget/1.0.0"
  "module-detail-export/1.0.3"
)

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
