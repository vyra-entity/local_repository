#!/usr/bin/env python3
"""
verify_plugins.py — Validate all plugins in the local repository.

Checks that each plugin version directory contains:
  • manifest.yaml        (required)
  • logic.wasm or ui/    (required if entry_points are defined)
  • schema.json          (optional — shown as info if missing)

Also validates manifest.yaml against schemas/plugin_manifest.schema.json.

Usage:
  # Verify plugins in local_repository/data/plugins/ (default)
  python tools/verify_plugins.py

  # Also check legacy plugins/ directory
  python tools/verify_plugins.py --legacy

  # Verify a specific plugins directory
  python tools/verify_plugins.py --plugins-dir /path/to/plugins

Exit code:
  0  All plugins pass validation
  1  One or more plugins have errors
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
DATA_DIR = REPO_ROOT / "data"

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# Terminal colours
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_CYAN = "\033[96m"
_BLUE = "\033[94m"


def _ok(msg: str) -> str:
    return f"{_GREEN}✅{_RESET} {msg}"


def _warn(msg: str) -> str:
    return f"{_YELLOW}⚠️ {_RESET} {msg}"


def _err(msg: str) -> str:
    return f"{_RED}❌{_RESET} {msg}"


def _info(msg: str) -> str:
    return f"{_BLUE}ℹ️ {_RESET} {msg}"


def load_schema(schema_path: Path) -> dict | None:
    """Load a JSON Schema from disk, or return None if unavailable."""
    if not schema_path.exists():
        return None
    try:
        return json.loads(schema_path.read_text())
    except json.JSONDecodeError as exc:
        print(_warn(f"Schema file malformed ({schema_path.name}): {exc}"))
        return None


def validate_manifest(manifest: dict, schema: dict | None) -> list[str]:
    """Return a list of validation error messages (empty if valid).

    Args:
        manifest: Parsed manifest.yaml content.
        schema: JSON Schema dict, or None to skip schema validation.
    """
    errors: list[str] = []
    if schema and _HAS_JSONSCHEMA:
        validator = jsonschema.Draft7Validator(schema)
        for error in validator.iter_errors(manifest):
            path = ".".join(str(p) for p in error.absolute_path) or "<root>"
            errors.append(f"{path}: {error.message}")
    return errors


def check_plugin_version(
    plugin_id: str,
    version: str,
    version_dir: Path,
    schema: dict | None,
) -> dict:
    """Check a single plugin/<id>/<version>/ directory.

    Args:
        plugin_id: Plugin identifier (directory name).
        version: Version string (directory name).
        version_dir: Absolute path to the version directory.
        schema: Optional JSON Schema for manifest.yaml validation.

    Returns:
        Result dict with keys: plugin_id, version, path, errors, warnings, info.
    """
    result: dict = {
        "plugin_id": plugin_id,
        "version": version,
        "path": str(version_dir),
        "errors": [],
        "warnings": [],
        "info": [],
        "manifest": {},
    }

    # ── manifest.yaml ─────────────────────────────────────────────────────
    manifest_path = version_dir / "manifest.yaml"
    if not manifest_path.exists():
        result["errors"].append("Missing manifest.yaml")
        return result

    if not _HAS_YAML:
        result["warnings"].append("pyyaml not installed — cannot parse manifest.yaml")
        return result

    try:
        manifest = yaml.safe_load(manifest_path.read_text()) or {}
    except yaml.YAMLError as exc:
        result["errors"].append(f"Invalid YAML in manifest.yaml: {exc}")
        return result

    result["manifest"] = manifest

    # Required fields
    for field in ("id", "name", "version"):
        if not manifest.get(field):
            result["errors"].append(f"manifest.yaml: required field '{field}' is missing")

    # Cross-check id/version with directory names
    if manifest.get("id") and manifest["id"] != plugin_id:
        result["warnings"].append(
            f"manifest.yaml 'id' ({manifest['id']}) does not match directory name ({plugin_id})"
        )
    if manifest.get("version") and manifest["version"] != version:
        result["warnings"].append(
            f"manifest.yaml 'version' ({manifest['version']}) does not match directory ({version})"
        )

    # scope field
    scope = manifest.get("scope")
    if not scope:
        result["errors"].append("manifest.yaml: 'scope' field is missing")
    elif not scope.get("type"):
        result["errors"].append("manifest.yaml: 'scope.type' field is missing")

    # Schema validation
    schema_errors = validate_manifest(manifest, schema)
    result["errors"].extend(schema_errors)

    # ── Entry point files ─────────────────────────────────────────────────
    entry_points = manifest.get("entry_points") or {}
    backend = entry_points.get("backend") or {}
    frontend = entry_points.get("frontend") or {}

    # Backend: check WASM file if defined
    if backend:
        backend_file = backend.get("file", "")
        if backend_file:
            # File path is relative to NFS pool root — check if it exists relative to version_dir
            # by stripping the plugins/<id>/<version>/ prefix
            local_path = version_dir / Path(backend_file).name
            if not local_path.exists():
                # Also try resolving relative to REPO_ROOT
                pool_path_parts = Path(backend_file).parts
                if len(pool_path_parts) >= 3:
                    relative = Path(*pool_path_parts[3:])
                    local_path = version_dir / relative
                if not local_path.exists() and not (version_dir / "logic.wasm").exists():
                    result["warnings"].append(
                        f"Backend file '{backend_file}' not found locally (may be in NFS pool only)"
                    )

    # Frontend: check ES module file if defined
    if frontend:
        frontend_file = frontend.get("file", "")
        if frontend_file:
            ui_dir = version_dir / "ui"
            if not ui_dir.exists():
                result["warnings"].append("No ui/ directory found for frontend entry point")

    # ── Optional files ────────────────────────────────────────────────────
    schema_file = version_dir / "schema.json"
    if schema_file.exists():
        try:
            json.loads(schema_file.read_text())
            result["info"].append("config schema.json present and valid JSON")
        except json.JSONDecodeError:
            result["errors"].append("schema.json is not valid JSON")
    else:
        result["info"].append("No schema.json (config validation disabled)")

    icon_file = version_dir / "icon.svg"
    if not icon_file.exists():
        result["info"].append("No icon.svg")

    return result


def check_plugins_dir(plugins_dir: Path, schema: dict | None, label: str) -> list[dict]:
    """Check all plugin/<id>/<version>/ directories.

    Args:
        plugins_dir: Root plugins directory to scan.
        schema: Optional JSON Schema for manifest.yaml.
        label: Label used in display output.

    Returns:
        List of result dicts.
    """
    results = []

    if not plugins_dir.exists():
        return results

    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        # Skip non-plugin directories (README, build scripts, etc.)
        if plugin_dir.name in ("README.md", "build_all.sh", "__pycache__"):
            continue

        for version_dir in sorted(plugin_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            result = check_plugin_version(plugin_dir.name, version_dir.name, version_dir, schema)
            result["source"] = label
            results.append(result)

    return results


def print_results(results: list[dict]) -> int:
    """Print a formatted summary and return 0 (pass) or 1 (fail)."""
    if not results:
        print(f"\n{_YELLOW}⚠️  No plugins found.{_RESET}")
        print(f"   Populate data/plugins/ or run: python tools/migrate_to_data.py")
        return 0

    all_pass = True

    # Group by source
    sources = {}
    for r in results:
        src = r.get("source", "unknown")
        sources.setdefault(src, []).append(r)

    for source_label, source_results in sources.items():
        print(f"\n{_BOLD}{_CYAN}Plugins — {source_label}{_RESET}")
        print("─" * 80)

        col_w = max((len(r["plugin_id"]) for r in source_results), default=0) + 2
        ver_w = max((len(r["version"]) for r in source_results), default=0) + 2

        header = f"  {'Plugin ID':<{col_w}} {'Version':<{ver_w}} Status   Name"
        print(f"{_BOLD}{header}{_RESET}")
        print("─" * 80)

        for r in source_results:
            pid = r["plugin_id"]
            ver = r["version"]
            manifest = r.get("manifest") or {}
            name = manifest.get("name", "")
            errors = r.get("errors", [])
            warnings = r.get("warnings", [])
            info = r.get("info", [])

            if errors:
                all_pass = False
                status = _err("FAIL")
            elif warnings:
                status = _warn("WARN")
            else:
                status = _ok("PASS")

            scope_type = (manifest.get("scope") or {}).get("type", "")
            scope_target = (manifest.get("scope") or {}).get("target", "")
            scope_str = f"  [{scope_type}:{scope_target}]" if scope_type else ""

            print(f"  {pid:<{col_w}} {ver:<{ver_w}} {status}  {name}{scope_str}")

            for e in errors:
                print(f"    {_RED}→ {e}{_RESET}")
            for w in warnings:
                print(f"    {_YELLOW}→ {w}{_RESET}")
            for i in info:
                print(f"    {_BLUE}ℹ {i}{_RESET}")

    # Summary
    total = len(results)
    failed = sum(1 for r in results if r.get("errors"))
    warned = sum(1 for r in results if r.get("warnings") and not r.get("errors"))

    print(f"\n{'─' * 80}")
    if all_pass:
        print(f"{_GREEN}{_BOLD}✅ All {total} plugin version(s) passed validation.{_RESET}")
    else:
        suffix = f"  {_YELLOW}({warned} with warnings){_RESET}" if warned else ""
        print(f"{_RED}{_BOLD}❌ {failed} of {total} plugin version(s) failed validation.{_RESET}{suffix}")

    if not _HAS_JSONSCHEMA:
        print(f"\n{_YELLOW}ℹ️  Install jsonschema for schema validation: pip install jsonschema{_RESET}")

    return 0 if all_pass else 1


def main() -> int:
    """Parse CLI arguments and run the verification."""
    parser = argparse.ArgumentParser(
        description="Validate VYRA plugin packages in the local repository.",
    )
    parser.add_argument(
        "--plugins-dir",
        default=str(DATA_DIR / "plugins"),
        help="Path to the repository plugins directory (default: data/plugins/)",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Also check the legacy plugins/ directory at the repository root.",
    )
    args = parser.parse_args()

    schema_path = SCHEMAS_DIR / "plugin_manifest.schema.json"
    schema = load_schema(schema_path)
    if schema:
        print(f"ℹ️   Using schema: {schema_path}")
    else:
        print(f"{_YELLOW}ℹ️   Schema not found at {schema_path} — structural checks only{_RESET}")

    all_results: list[dict] = []

    # Primary directory (data/plugins/)
    plugins_dir = Path(args.plugins_dir)
    results = check_plugins_dir(plugins_dir, schema, f"data/plugins/ ({plugins_dir})")
    all_results.extend(results)

    # Legacy directory (plugins/)
    if args.legacy:
        legacy_dir = REPO_ROOT / "plugins"
        if legacy_dir.exists():
            legacy_results = check_plugins_dir(legacy_dir, schema, f"plugins/ (legacy)")
            all_results.extend(legacy_results)
        else:
            print(f"{_YELLOW}⚠️   --legacy specified but plugins/ not found at {legacy_dir}{_RESET}")

    return print_results(all_results)


if __name__ == "__main__":
    sys.exit(main())
