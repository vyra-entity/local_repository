#!/usr/bin/env python3
"""
verify_modules.py — Validate all modules in the local repository.

Checks that each module version directory contains:
  • metadata.json        (required)
  • <name>_<version>.tar.gz  (required)
  • images/              (optional — shown as warning if missing)

Also validates metadata.json against schemas/module_data.schema.json.

Usage:
  # Verify modules in local_repository/data/modules/ (default)
  python tools/verify_modules.py

  # Verify a specific modules directory
  python tools/verify_modules.py --modules-dir /path/to/data/modules

  # Also check for source modules in VOS2_WORKSPACE/modules/
  python tools/verify_modules.py --check-source

Exit code:
  0  All modules pass validation
  1  One or more modules have errors
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
DATA_DIR = REPO_ROOT / "data"
WORKSPACE_ROOT = REPO_ROOT.parent

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


def _ok(msg: str) -> str:
    return f"{_GREEN}✅{_RESET} {msg}"


def _warn(msg: str) -> str:
    return f"{_YELLOW}⚠️ {_RESET} {msg}"


def _err(msg: str) -> str:
    return f"{_RED}❌{_RESET} {msg}"


def load_schema(schema_path: Path) -> dict | None:
    """Load a JSON Schema from disk, or return None if unavailable."""
    if not schema_path.exists():
        return None
    try:
        return json.loads(schema_path.read_text())
    except json.JSONDecodeError as exc:
        print(_warn(f"Schema file malformed ({schema_path.name}): {exc}"))
        return None


def validate_metadata(meta: dict, schema: dict | None) -> list[str]:
    """Return a list of validation error messages (empty if valid)."""
    errors: list[str] = []
    if schema and _HAS_JSONSCHEMA:
        validator = jsonschema.Draft7Validator(schema)
        for error in validator.iter_errors(meta):
            errors.append(f"{'.'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}")
    return errors


def check_source_modules(workspace_modules: Path, schema: dict | None) -> list[dict]:
    """Check source module directories for required .module/module_data.yaml.

    Args:
        workspace_modules: Path to VOS2_WORKSPACE/modules/.
        schema: Optional JSON schema to validate module_data.yaml against.

    Returns:
        List of result dicts per source module.
    """
    results = []
    if not workspace_modules.exists():
        return results

    for module_dir in sorted(workspace_modules.glob("v2_*")):
        if not module_dir.is_dir():
            continue
        module_data_path = module_dir / ".module" / "module_data.yaml"
        result: dict = {
            "type": "source",
            "path": str(module_dir),
            "dir_name": module_dir.name,
            "errors": [],
            "warnings": [],
        }
        if not module_data_path.exists():
            result["errors"].append("Missing .module/module_data.yaml")
            results.append(result)
            continue

        if not _HAS_YAML:
            result["warnings"].append("pyyaml not installed — cannot validate module_data.yaml")
            results.append(result)
            continue

        try:
            data = yaml.safe_load(module_data_path.read_text()) or {}
        except yaml.YAMLError as exc:
            result["errors"].append(f"Invalid YAML in module_data.yaml: {exc}")
            results.append(result)
            continue

        result["name"] = data.get("name", "?")
        result["version"] = data.get("version", "?")
        result["uuid"] = data.get("uuid", "?")

        schema_errors = validate_metadata(data, schema)
        result["errors"].extend(schema_errors)

        if not data.get("name"):
            result["errors"].append("module_data.yaml: 'name' field is missing")
        if not data.get("version"):
            result["errors"].append("module_data.yaml: 'version' field is missing")
        if not data.get("uuid"):
            result["errors"].append("module_data.yaml: 'uuid' field is missing")

        results.append(result)

    return results


def check_repository_modules(modules_dir: Path, schema: dict | None) -> list[dict]:
    """Check exported modules directory for required files.

    Args:
        modules_dir: Path to data/modules/ or similar.
        schema: Optional JSON schema for metadata.json validation.

    Returns:
        List of result dicts per module/version.
    """
    results = []

    if not modules_dir.exists():
        return results

    for name_dir in sorted(modules_dir.iterdir()):
        if not name_dir.is_dir():
            continue

        for version_dir in sorted(name_dir.iterdir()):
            if not version_dir.is_dir():
                continue

            name = name_dir.name
            version = version_dir.name
            result: dict = {
                "type": "repository",
                "name": name,
                "version": version,
                "path": str(version_dir),
                "errors": [],
                "warnings": [],
            }

            # Check metadata.json
            metadata_path = version_dir / "metadata.json"
            if not metadata_path.exists():
                result["errors"].append("Missing metadata.json")
            else:
                try:
                    meta = json.loads(metadata_path.read_text())
                except json.JSONDecodeError as exc:
                    result["errors"].append(f"Invalid JSON in metadata.json: {exc}")
                    meta = {}

                if meta:
                    schema_errors = validate_metadata(meta, schema)
                    result["errors"].extend(schema_errors)

                    # Cross-check directory name vs metadata
                    if meta.get("name") and meta["name"] != name:
                        result["warnings"].append(
                            f"metadata.json 'name' ({meta['name']}) does not match directory ({name})"
                        )
                    if meta.get("version") and meta["version"] != version:
                        result["warnings"].append(
                            f"metadata.json 'version' ({meta['version']}) does not match directory ({version})"
                        )

            # Check archive file
            archive = version_dir / f"{name}_{version}.tar.gz"
            if not archive.exists():
                result["errors"].append(f"Missing archive: {name}_{version}.tar.gz")
            else:
                size_mb = archive.stat().st_size / 1024 / 1024
                result["archive_size_mb"] = round(size_mb, 2)

            # Check images directory (optional)
            images_dir = version_dir / "images"
            if images_dir.exists():
                image_files = list(images_dir.glob("*.tar.gz"))
                result["image_count"] = len(image_files)
                if not image_files:
                    result["warnings"].append("images/ directory exists but contains no .tar.gz files")
            else:
                result["warnings"].append("No images/ directory (Docker images not exported)")

            results.append(result)

    return results


def print_results(
    repo_results: list[dict],
    source_results: list[dict],
) -> int:
    """Print a formatted summary table and return 0 (pass) or 1 (fail)."""
    all_pass = True

    # ── Repository modules ────────────────────────────────────────────────
    if repo_results:
        print(f"\n{_BOLD}{_CYAN}Repository Modules (data/modules/){_RESET}")
        print("─" * 70)

        col_w = max((len(r.get("name", "")) for r in repo_results), default=0) + 2
        ver_w = max((len(r.get("version", "")) for r in repo_results), default=0) + 2

        header = f"  {'Name':<{col_w}} {'Version':<{ver_w}} Status"
        print(f"{_BOLD}{header}{_RESET}")
        print("─" * 70)

        for r in repo_results:
            name = r.get("name", "?")
            version = r.get("version", "?")
            errors = r.get("errors", [])
            warnings = r.get("warnings", [])

            info_parts = []
            if r.get("archive_size_mb"):
                info_parts.append(f"{r['archive_size_mb']} MB")
            if r.get("image_count") is not None:
                info_parts.append(f"{r['image_count']} image(s)")
            info = f"  ({', '.join(info_parts)})" if info_parts else ""

            if errors:
                all_pass = False
                status = _err("FAIL")
            elif warnings:
                status = _warn("WARN")
            else:
                status = _ok("PASS")

            print(f"  {name:<{col_w}} {version:<{ver_w}} {status}{info}")

            for e in errors:
                print(f"    {_RED}→ {e}{_RESET}")
            for w in warnings:
                print(f"    {_YELLOW}→ {w}{_RESET}")
    else:
        print(f"\n{_YELLOW}⚠️  No repository modules found in data/modules/{_RESET}")
        print(f"   Run: python tools/export_module.py --import-to data/")
        print(f"   Or:  python tools/migrate_to_data.py")

    # ── Source modules ────────────────────────────────────────────────────
    if source_results:
        print(f"\n{_BOLD}{_CYAN}Source Modules (VOS2_WORKSPACE/modules/){_RESET}")
        print("─" * 70)

        col_w = max((len(r.get("name", r["dir_name"])[:40]) for r in source_results), default=0) + 2

        for r in source_results:
            name = r.get("name") or r["dir_name"]
            version = r.get("version", "?")
            errors = r.get("errors", [])
            warnings = r.get("warnings", [])

            if errors:
                all_pass = False
                status = _err("FAIL")
            elif warnings:
                status = _warn("WARN")
            else:
                status = _ok("PASS")

            print(f"  {name[:40]:<{col_w}} v{version:<12} {status}")
            for e in errors:
                print(f"    {_RED}→ {e}{_RESET}")
            for w in warnings:
                print(f"    {_YELLOW}→ {w}{_RESET}")

    # ── Summary ───────────────────────────────────────────────────────────
    total = len(repo_results) + len(source_results)
    failed = sum(1 for r in (repo_results + source_results) if r.get("errors"))
    warned = sum(1 for r in (repo_results + source_results) if r.get("warnings") and not r.get("errors"))

    print(f"\n{'─' * 70}")
    if all_pass:
        print(f"{_GREEN}{_BOLD}✅ All {total} module(s) passed validation.{_RESET}")
    else:
        print(
            f"{_RED}{_BOLD}❌ {failed} of {total} module(s) failed validation.{_RESET}"
            + (f"  {_YELLOW}({warned} with warnings){_RESET}" if warned else "")
        )

    if not _HAS_JSONSCHEMA:
        print(f"\n{_YELLOW}ℹ️  Install jsonschema for schema-based validation: pip install jsonschema{_RESET}")

    return 0 if all_pass else 1


def main() -> int:
    """Parse CLI arguments and run the verification."""
    parser = argparse.ArgumentParser(
        description="Validate VYRA module packages in the local repository.",
    )
    parser.add_argument(
        "--modules-dir",
        default=str(DATA_DIR / "modules"),
        help="Path to the repository modules directory (default: data/modules/)",
    )
    parser.add_argument(
        "--check-source",
        action="store_true",
        help="Also validate source module directories in VOS2_WORKSPACE/modules/.",
    )
    parser.add_argument(
        "--workspace",
        default=str(WORKSPACE_ROOT / "modules"),
        help="Path to VOS2_WORKSPACE/modules/ when --check-source is set.",
    )
    args = parser.parse_args()

    schema_path = SCHEMAS_DIR / "module_data.schema.json"
    schema = load_schema(schema_path)
    if schema:
        print(f"ℹ️   Using schema: {schema_path}")
    else:
        print(f"{_YELLOW}ℹ️   Schema not found at {schema_path} — structural checks only{_RESET}")

    modules_dir = Path(args.modules_dir)
    repo_results = check_repository_modules(modules_dir, schema)

    source_results: list[dict] = []
    if args.check_source:
        workspace_modules = Path(args.workspace)
        source_results = check_source_modules(workspace_modules, schema)

    return print_results(repo_results, source_results)


if __name__ == "__main__":
    sys.exit(main())
