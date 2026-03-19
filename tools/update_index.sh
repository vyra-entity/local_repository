#!/usr/bin/env bash
# update_index.sh
# ---------------------------------------------------------------------------
# Scans local_repository/modules/<name>/<version>/metadata.json
#        and local_repository/plugins/<name>/<version>/manifest.yaml
# and rebuilds the modules/plugins arrays in index.json.
#
# Multiple versions of the same module or plugin are written as SEPARATE
# entries so that the v2_modulemanager UI can group them by id/name and
# render a version-selector dropdown at install time.
#
# Usage:
#   cd /path/to/local_repository
#   ./update_index.sh [--dry-run]
#
# Requirements:  python3 with pyyaml  (pip install pyyaml)
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INDEX_FILE="$REPO_ROOT/index.json"
MODULES_DIR="$REPO_ROOT/modules"
PLUGINS_DIR="$REPO_ROOT/plugins"
DRY_RUN=false

for arg in "$@"; do
  [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
done

echo "🔍  Scanning local repository at: $REPO_ROOT"
[[ "$DRY_RUN" == true ]] && echo "    (dry-run mode — index.json will NOT be modified)"

# ── Require python3 ──────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  python3 is required but was not found." >&2
  exit 1
fi

# ── Check for PyYAML ─────────────────────────────────────────────────────────
if ! python3 -c "import yaml" 2>/dev/null; then
  echo "⚠   PyYAML not found — attempting to install via pip..."
  python3 -m pip install --quiet pyyaml
fi

# ── Run the Python update logic ──────────────────────────────────────────────
python3 - "$INDEX_FILE" "$MODULES_DIR" "$PLUGINS_DIR" "$DRY_RUN" <<'PYEOF'
"""
Read all metadata.json (modules) and manifest.yaml (plugins) files and
rebuild the modules/plugins arrays in index.json.

Each <name>/<version>/ directory produces one entry.  Entries with the same
name/id but different versions are intentionally kept as separate objects so
the v2_modulemanager browser UI can group them and offer a version selector.
"""
import sys
import json
import os
import datetime

try:
    import yaml
except ImportError:
    print("❌  PyYAML is not available.  Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

INDEX_FILE = sys.argv[1]
MODULES_DIR = sys.argv[2]
PLUGINS_DIR = sys.argv[3]
DRY_RUN = sys.argv[4].lower() == "true"


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    """Load and return a JSON file."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_yaml(path: str) -> dict:
    """Load and return a YAML file using PyYAML safe_load."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def semver_key(version_str: str):
    """Return a tuple for semantic-version sorting (handles non-numeric parts)."""
    parts = []
    for part in str(version_str).split("."):
        try:
            parts.append((0, int(part)))
        except ValueError:
            parts.append((1, part))
    return parts


def file_exists_relative(base: str, rel_path: str) -> bool:
    """Return True if base/rel_path exists on disk."""
    return os.path.isfile(os.path.join(base, rel_path))


# ── Scan modules ─────────────────────────────────────────────────────────────

def scan_modules(modules_dir: str) -> list:
    """
    Walk modules/<name>/<version>/metadata.json and return a list of module
    entry dicts ready to be written into index.json.
    """
    entries = []
    if not os.path.isdir(modules_dir):
        print(f"  ⚠  modules directory not found: {modules_dir}")
        return entries

    for module_name in sorted(os.listdir(modules_dir)):
        module_path = os.path.join(modules_dir, module_name)
        if not os.path.isdir(module_path):
            continue

        versions = sorted(
            (v for v in os.listdir(module_path) if os.path.isdir(os.path.join(module_path, v))),
            key=semver_key,
        )
        for version in versions:
            ver_path = os.path.join(module_path, version)
            meta_file = os.path.join(ver_path, "metadata.json")

            if not os.path.isfile(meta_file):
                print(f"  ⚠  No metadata.json in {ver_path} — skipped.")
                continue

            try:
                meta = load_json(meta_file)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  ❌  Cannot parse {meta_file}: {exc}")
                continue

            entries.append(meta)
            print(f"  ✅  module  {module_name}  {version}")

    return entries


# ── Scan plugins ─────────────────────────────────────────────────────────────

def normalize_plugin_entry(manifest: dict, plugin_name: str, version: str, repo_root: str) -> dict:
    """
    Convert a manifest.yaml dict into the plugin entry schema used in index.json.
    Only top-level fields that are present in the manifest are written; missing
    optional fields are omitted to keep the JSON lean.
    """
    entry = {
        "id":           manifest.get("id", plugin_name),
        "name":         manifest.get("name", plugin_name),
        "version":      str(manifest.get("version", version)),
        "description":  str(manifest.get("description", "")).strip(),
        "author":       manifest.get("author", ""),
        "status":       manifest.get("status", "development"),
        "priority":     manifest.get("priority", 50),
        "load_strategy": manifest.get("load_strategy", "eager"),
        "scope":        manifest.get("scope", {}),
        "compatible_with": manifest.get("compatible_with", []),
        "manifest_path": f"plugins/{plugin_name}/{version}/manifest.yaml",
        "checksum":     manifest.get("checksum", ""),
        "hash":         manifest.get("hash", ""),
    }

    # Include icon path only when the file actually exists
    icon_rel = f"plugins/{plugin_name}/{version}/icon.svg"
    if file_exists_relative(repo_root, icon_rel):
        entry["icon"] = icon_rel

    # Include config_schema path when present
    schema_rel = f"plugins/{plugin_name}/{version}/schema.json"
    if file_exists_relative(repo_root, schema_rel):
        entry["config_schema"] = schema_rel

    return entry


def scan_plugins(plugins_dir: str, repo_root: str) -> list:
    """
    Walk plugins/<name>/<version>/manifest.yaml and return a list of plugin
    entry dicts ready to be written into index.json.
    """
    entries = []
    if not os.path.isdir(plugins_dir):
        print(f"  ⚠  plugins directory not found: {plugins_dir}")
        return entries

    for plugin_name in sorted(os.listdir(plugins_dir)):
        plugin_path = os.path.join(plugins_dir, plugin_name)
        if not os.path.isdir(plugin_path):
            continue  # skip README.md etc.

        versions = sorted(
            (v for v in os.listdir(plugin_path) if os.path.isdir(os.path.join(plugin_path, v))),
            key=semver_key,
        )
        for version in versions:
            ver_path = os.path.join(plugin_path, version)
            manifest_file = os.path.join(ver_path, "manifest.yaml")

            if not os.path.isfile(manifest_file):
                print(f"  ⚠  No manifest.yaml in {ver_path} — skipped.")
                continue

            try:
                manifest = load_yaml(manifest_file)
            except Exception as exc:
                print(f"  ❌  Cannot parse {manifest_file}: {exc}")
                continue

            entry = normalize_plugin_entry(manifest, plugin_name, version, repo_root)
            entries.append(entry)
            print(f"  ✅  plugin  {plugin_name}  {version}")

    return entries


# ── Main ─────────────────────────────────────────────────────────────────────

repo_root = os.path.dirname(INDEX_FILE)

# Load existing index.json to preserve header metadata
try:
    index = load_json(INDEX_FILE)
except (FileNotFoundError, json.JSONDecodeError) as exc:
    print(f"❌  Cannot read {INDEX_FILE}: {exc}", file=sys.stderr)
    sys.exit(1)

print("\n── Modules ────────────────────────────────────────────────────────────────")
new_modules = scan_modules(MODULES_DIR)

print("\n── Plugins ────────────────────────────────────────────────────────────────")
new_plugins = scan_plugins(PLUGINS_DIR, repo_root)

# Update only the dynamic fields; preserve name/description/version/type/base_url
index["last_updated"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
index["modules"] = new_modules
index["plugins"] = new_plugins

summary = (
    f"\n✅  Found {len(new_modules)} module version(s) and "
    f"{len(new_plugins)} plugin version(s)."
)
print(summary)

if DRY_RUN:
    print("\n── Dry-run output ─────────────────────────────────────────────────────────")
    print(json.dumps(index, indent=2, ensure_ascii=False))
else:
    with open(INDEX_FILE, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"📝  index.json written to: {INDEX_FILE}")

PYEOF
