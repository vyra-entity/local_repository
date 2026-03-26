#!/usr/bin/env python3
"""
sync_from_modules.py
Synchronisiert Module aus dem /modules Ordner in das lokale Repository.

Neue Struktur:
  modules/{module_name}/{version}/metadata.json
  modules/{module_name}/{version}/{module_name}_{version}.tar.gz
  modules/{module_name}/{version}/images/{variant}.tar.gz  (delta or full)
  plugins/
  index.json

Verwendung:
  # Alle Module synchronisieren
  python3 tools/sync_from_modules.py [PFAD_ZU_MODULES]

  # Einzelnes Modul synchronisieren
  python3 tools/sync_from_modules.py --module /path/to/v2_usermanager_<hash>

  # Vollständige Images statt Delta-Archives packen
  python3 tools/sync_from_modules.py --store-full-image
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 'pyyaml' fehlt. Installieren: pip install pyyaml")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent

# Dateien/Verzeichnisse die beim Packen ausgeschlossen werden
EXCLUDES = {
    "storage/certificates",
    "node_modules",
    ".git",
    ".github",
    ".bak",
    ".gitignore",
    ".vscode",
}

# ---------------------------------------------------------------------------
# Docker image utilities
# ---------------------------------------------------------------------------

# Candidate image variants to probe for each module.
# Full modules (VYRA_SLIM=false): development, production
# Slim modules (VYRA_SLIM=true):  slim-development, slim-production
_FULL_VARIANTS = ["development", "production"]
_SLIM_VARIANTS = ["slim-development", "slim-production"]

# Known base images (runtime images for each variant tag)
_BASE_IMAGE_MAP = {
    "development": "vyra_base_image:development",
    "production": "vyra_base_image:production",
    "slim-development": "vyra_base_image_slim:development",
    "slim-production": "vyra_base_image_slim:production",
}


def _run_docker(*args: str) -> subprocess.CompletedProcess:
    """Run a docker command; stderr is captured but not raised."""
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
    )


def _image_exists(tag: str) -> bool:
    """Return True if a Docker image tag is available locally."""
    result = _run_docker("image", "inspect", tag)
    return result.returncode == 0


def _get_image_label(tag: str, label_key: str) -> str | None:
    """Read a single label value from a Docker image."""
    fmt = f'{{{{index .Config.Labels "{label_key}"}}}}'
    result = _run_docker("inspect", "--format", fmt, tag)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value if value else None


def _get_image_layer_ids(tag: str) -> list[str]:
    """Return the ordered diff_ids (layer chain) of a Docker image."""
    result = _run_docker("inspect", "--format", "{{json .RootFS.Layers}}", tag)
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout.strip()) or []
    except json.JSONDecodeError:
        return []


def _export_full_image(image_tag: str, output_path: Path) -> None:
    """Export a complete Docker image as a gzip-compressed tar archive."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tar.gz.tmp")
    try:
        save_proc = subprocess.Popen(
            ["docker", "save", image_tag],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        with open(tmp_path, "wb") as out_f:
            with gzip.GzipFile(fileobj=out_f, mode="wb") as gz_f:
                for chunk in iter(lambda: save_proc.stdout.read(65536), b""):
                    gz_f.write(chunk)
        save_proc.wait()
        if save_proc.returncode != 0:
            err = save_proc.stderr.read().decode()
            raise RuntimeError(f"docker save failed: {err}")
        tmp_path.rename(output_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _export_delta_image(
    module_image: str,
    base_image: str,
    output_path: Path,
) -> None:
    """Export only the layers added on top of base_image as a delta archive.

    The delta archive contains:
      - manifest.json        — original full manifest (all layers listed)
      - <config_hash>.json   — full image config
      - base_info.json       — base image name, version, and layer count K
      - only the delta layer tar files (layers[K:])

    The container_manager reconstructs a loadable tar by merging the base
    image layers with this delta when installing.

    Args:
        module_image: Full tag of the module image to export.
        base_image: Full tag of the base image the module was built on.
        output_path: Destination .tar.gz path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tar.gz.tmp")
    tmp_path.unlink(missing_ok=True)

    module_layers = _get_image_layer_ids(module_image)
    base_layers = _get_image_layer_ids(base_image)

    if not module_layers:
        raise RuntimeError(f"Cannot read layers from {module_image}")
    if not base_layers:
        raise RuntimeError(f"Cannot read layers from {base_image}")

    # Verify layer prefix
    if module_layers[: len(base_layers)] != base_layers:
        raise RuntimeError(
            f"{module_image} layers do not start with {base_image} layers — "
            "cannot create delta. Use --store-full-image."
        )

    K = len(base_layers)
    base_version = _get_image_label(base_image, "org.opencontainers.image.version") or ""

    # docker save the full image into a temp dir so we can cherry-pick layers
    with tempfile.TemporaryDirectory(prefix="vyra_delta_") as tmpdir:
        raw_tar = Path(tmpdir) / "full.tar"
        save_proc = subprocess.run(
            ["docker", "save", module_image, "-o", str(raw_tar)],
            capture_output=True,
        )
        if save_proc.returncode != 0:
            raise RuntimeError(f"docker save failed: {save_proc.stderr.decode()}")

        with tarfile.open(raw_tar, "r") as full_tar:
            # Read manifest
            manifest_data = json.loads(full_tar.extractfile("manifest.json").read())
            manifest_entry = manifest_data[0]
            config_path = manifest_entry["Config"]  # e.g. "abc123.json"
            all_layer_paths = manifest_entry["Layers"]  # ["<hash>/layer.tar", ...]

            if len(all_layer_paths) != len(module_layers):
                raise RuntimeError(
                    f"Layer count mismatch: manifest has {len(all_layer_paths)}, "
                    f"inspect has {len(module_layers)}"
                )

            delta_layer_paths = all_layer_paths[K:]  # only new layers

            base_info = {
                "base_image": base_image,
                "base_version": base_version,
                "base_layer_count": K,
                "module_image": module_image,
            }

            # Write delta archive
            try:
                with gzip.open(tmp_path, "wb") as gz_f:
                    with tarfile.open(fileobj=gz_f, mode="w|") as delta_tar:  # type: ignore[arg-type]
                        # manifest.json (full — needed for docker load reconstruction)
                        manifest_bytes = json.dumps(manifest_data, indent=2).encode()
                        _add_bytes_to_tar(delta_tar, "manifest.json", manifest_bytes)

                        # image config (full)
                        config_member = full_tar.getmember(config_path)
                        config_f = full_tar.extractfile(config_member)
                        delta_tar.addfile(config_member, config_f)

                        # base_info.json (new)
                        base_info_bytes = json.dumps(base_info, indent=2).encode()
                        _add_bytes_to_tar(delta_tar, "base_info.json", base_info_bytes)

                        # only delta layers
                        for layer_path in delta_layer_paths:
                            member = full_tar.getmember(layer_path)
                            layer_f = full_tar.extractfile(member)
                            delta_tar.addfile(member, layer_f)

                tmp_path.rename(output_path)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise


def _add_bytes_to_tar(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    """Add raw bytes as a named entry to an open TarFile."""
    import io

    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _read_env_value(env_file: Path, key: str, default: str = "") -> str:
    """Read a single key=value line from a .env file."""
    if not env_file.exists():
        return default
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                value = line.split("=", 1)[1].split("#")[0].strip()
                return value
    return default


def _pack_module_images(
    module_dir: Path,
    version_dir: Path,
    module_name: str,
    store_full: bool = False,
) -> dict:
    """Export Docker images for a module into version_dir/images/.

    Probes 4 candidate image tags and exports those that exist locally.
    Full modules (VYRA_SLIM=false) use 'development'/'production' tags.
    Slim modules (VYRA_SLIM=true) use 'slim-development'/'slim-production'.

    Production variants are required; missing development variants produce a
    warning but do not abort.  If ALL production variants are missing the
    module is considered unbuildable and a RuntimeError is raised.

    Args:
        module_dir: Module source directory.
        version_dir: Destination version directory in the repository.
        module_name: Module base name (without UUID).
        store_full: When True, export full images; otherwise export delta archives.

    Returns:
        Dict mapping variant → {filename, base_image, base_version, archive_type}
    """
    images_dir = version_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    env_file = module_dir / ".env"
    is_slim = _read_env_value(env_file, "VYRA_SLIM", "false").lower() == "true"
    candidates = _SLIM_VARIANTS if is_slim else _FULL_VARIANTS

    production_tag = "slim-production" if is_slim else "production"
    development_tag = "slim-development" if is_slim else "development"

    images_meta: dict = {}

    for variant in candidates:
        image_tag = f"{module_name}:{variant}"
        is_prod = production_tag in variant

        if not _image_exists(image_tag):
            if is_prod:
                # production variant is required
                raise RuntimeError(
                    f"❌ Required image '{image_tag}' not found locally.\n"
                    f"   Build it first: cd VOS2_WORKSPACE && ./tools/vyra_up.sh\n"
                    f"   Or for a single module: docker build -t {image_tag} ..."
                )
            else:
                print(f"   ⚠️  Development image '{image_tag}' not found — packing without it")
                continue

        base_image = _BASE_IMAGE_MAP.get(variant)
        base_version = ""
        if base_image:
            base_version = _get_image_label(base_image, "org.opencontainers.image.version") or ""

        archive_name = f"{module_name}_{variant}.tar.gz"
        archive_path = images_dir / archive_name
        relative_path = f"modules/{module_name}/{version_dir.name}/images/{archive_name}"

        print(f"   🐳 Exporting image '{image_tag}' ({'full' if store_full else 'delta'}) ...")
        if store_full or not base_image or not _image_exists(base_image):
            if not store_full and base_image and not _image_exists(base_image):
                print(f"   ⚠️  Base image '{base_image}' not found; falling back to full export")
            _export_full_image(image_tag, archive_path)
            archive_type = "full"
        else:
            try:
                _export_delta_image(image_tag, base_image, archive_path)
                archive_type = "delta"
            except RuntimeError as exc:
                print(f"   ⚠️  Delta export failed ({exc}); falling back to full export")
                print(f"   ℹ️  Full export of '{image_tag}' may take several minutes for large images — please wait ...")
                _export_full_image(image_tag, archive_path)
                archive_type = "full"

        images_meta[variant] = {
            "filename": relative_path,
            "image_tag": image_tag,
            "base_image": base_image or "",
            "base_version": base_version,
            "archive_type": archive_type,
        }
        print(f"   ✅ Image packed: {archive_name} (type={archive_type})")

    return images_meta


def sha256_file(path: Path) -> str:
    """Berechne SHA256-Prüfsumme einer Datei."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_excluded(member_name: str) -> bool:
    """Prüfe ob ein Pfad von der Archivierung ausgeschlossen werden soll."""
    for excl in EXCLUDES:
        if excl in member_name:
            return True
    return False


def pack_module(source_dir: Path, output_tar: Path) -> None:
    """Packt ein Modul-Verzeichnis als .tar.gz."""
    tmp_file = output_tar.with_suffix(".tar.gz.tmp")
    tmp_file.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tmp_file, "w:gz") as tar:
        for item in source_dir.rglob("*"):
            rel = item.relative_to(source_dir)
            rel_str = str(rel)
            if is_excluded(rel_str):
                continue
            tar.add(item, arcname=rel_str)

    tmp_file.rename(output_tar)


def read_module_data(module_dir: Path) -> dict:
    """Lese .module/module_data.yaml aus einem Modulverzeichnis."""
    yaml_file = module_dir / ".module" / "module_data.yaml"
    if not yaml_file.exists():
        return {}
    with open(yaml_file, "r") as f:
        return yaml.safe_load(f) or {}


def read_module_flags(module_dir: Path) -> dict:
    """Lese ENABLE_* Flags aus der .env Datei."""
    flags = {"frontend_active": False, "backend_active": False}
    env_file = module_dir / ".env"
    if not env_file.exists():
        return flags
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line == "ENABLE_FRONTEND_WEBSERVER=true":
                flags["frontend_active"] = True
            elif line in ("ENABLE_BACKEND_API=true", "ENABLE_BACKEND_WEBSERVER=true"):
                flags["backend_active"] = True
    return flags


def strip_uuid_suffix(name: str) -> str:
    """Entferne UUID-Suffix aus Modulname, z.B. v2_dashboard_aef036f... → v2_dashboard."""
    return re.sub(r"_[a-f0-9]{32}$", "", name)


def get_uuid_suffix(name: str) -> str:
    """Extrahiere UUID-Suffix aus Modulname."""
    match = re.search(r"([a-f0-9]{32})$", name)
    return match.group(1) if match else ""


def _sync_one_module(
    module_dir: Path,
    modules_dir: Path | None = None,
    ignore_filters: bool = False,
    store_full: bool = False,
) -> dict | None:
    """Process and sync one module directory into the repository.

    Args:
        module_dir: Absolute path to the module directory.
        modules_dir: Parent modules directory used to look for pre-built archives.
                     Falls back to module_dir.parent when not provided.
        ignore_filters: When True, skips the modulemanager/template exclusion
                        checks so any module path can be synced explicitly.
        store_full: When True, export complete Docker images instead of delta archives.

    Returns:
        The metadata dict that was written, or None when the module was skipped.
    """
    import shutil

    if modules_dir is None:
        modules_dir = module_dir.parent

    dir_name = module_dir.name

    if not ignore_filters:
        if "modulemanager" in dir_name:
            print(f"⏭️  Überspringe Modulemanager: {dir_name}")
            return None

    # Read metadata
    data = read_module_data(module_dir)
    if not data:
        print(f"⚠️  Keine module_data.yaml gefunden: {dir_name}")
        return None

    name = data.get("name") or strip_uuid_suffix(dir_name)

    if not ignore_filters and "template" in name:
        print(f"⏭️  Überspringe Template-Modul: {name}")
        return None

    version = data.get("version", "0.0.0")
    description = str(data.get("description") or "").replace("\n", " ").strip()
    author = str(data.get("author") or "")
    raw_template = data.get("template") or "basic"
    if isinstance(raw_template, list):
        template: list = [str(t).strip() for t in raw_template if str(t).strip()]
    else:
        template = [t.strip() for t in str(raw_template).split(",") if t.strip()]
    if not template:
        template = ["basic"]
    icon = str(data.get("icon") or "")
    dependencies = data.get("dependencies") or []
    # Try to extract UUID from directory name; fall back to parent dir name
    # (covers the new module-storages/<name>_<uuid>/<version>/ layout)
    version_hash = get_uuid_suffix(dir_name) or get_uuid_suffix(module_dir.parent.name)
    # Also try to read uuid from module_data.yaml as a last resort
    if not version_hash:
        version_hash = str(data.get("uuid") or "").replace("-", "").lower()[:32]
    flags = read_module_flags(module_dir)

    # Destination: modules/{name}/{version}/
    version_dir = REPO_DIR / "modules" / name / version
    version_dir.mkdir(parents=True, exist_ok=True)

    archive_name = f"{name}_{version}.tar.gz"
    archive_path = version_dir / archive_name
    relative_filename = f"modules/{name}/{version}/{archive_name}"

    # Check for a pre-built archive next to the module directory
    prebuilt = modules_dir / archive_name
    metadata_path = version_dir / "metadata.json"

    if prebuilt.exists():
        print(f"📦 Gefunden (vorgebaut): {archive_name}")
        if archive_path.exists() and archive_path.stat().st_size == prebuilt.stat().st_size and metadata_path.exists():
            print(f"   - ⏭️  Überspringe (identisch)")
            return None
        shutil.copy2(prebuilt, archive_path)
    else:
        print(f"📦 Packe: {dir_name}")
        print(f"   - 📁 Quelle: {module_dir}")
        if archive_path.exists():
            mod_time = max(
                (f.stat().st_mtime for f in module_dir.rglob("*") if f.is_file()),
                default=0,
            )
            if archive_path.stat().st_mtime >= mod_time and metadata_path.exists():
                print(f"   - ⏭️  Überspringe (kein Update)")
                return None
            print(f"   - ♻️  Update (Modul hat sich geändert)")
        pack_module(module_dir, archive_path)
        print(f"   - ✅ Packen erfolgreich")

    checksum = sha256_file(archive_path)
    size = archive_path.stat().st_size
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # metadata_path is already defined above (used for skip-check)
    # --- Pack Docker images --------------------------------------------------
    images_meta: dict = {}
    base_image_dep: dict | None = None
    try:
        images_meta = _pack_module_images(module_dir, version_dir, name, store_full)
        # Build a base_image dependency constraint from the packed image metadata
        for variant_info in images_meta.values():
            bv = variant_info.get("base_version")
            bi = variant_info.get("base_image", "").split(":")[0]
            if bv and bi:
                base_image_dep = {
                    "type": "base_image",
                    "name": bi,
                    "version": f">={bv}",
                }
                break
    except RuntimeError as exc:
        print(f"   ⚠️  Docker-Images nicht verfügbar (kein lokales Build): {exc}")
        print(f"   ℹ️  metadata.json wird ohne Images geschrieben.")
    except Exception as exc:
        print(f"   ⚠️  Image-Warnung (nicht fatal): {exc}")

    # Inject auto-detected base_image dependency if not already present
    if base_image_dep:
        existing_dep_names = {
            d.get("name") for d in dependencies if isinstance(d, dict)
        }
        if base_image_dep["name"] not in existing_dep_names:
            dependencies.append(base_image_dep)

    metadata = {
        "name": name,
        "version": version,
        "hash": version_hash,
        "description": description,
        "author": author,
        "template": template,
        "icon": icon,
        "dependencies": dependencies,
        "flags": flags,
        "filename": relative_filename,
        "images": images_meta,
        "synced_at": synced_at,
        "size": size,
        "checksum": checksum,
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"   - ✅ Synchronisiert: {name} v{version}")
    print()
    return metadata


def sync_modules(modules_dir: Path, store_full: bool = False) -> list:
    """Sync all modules from modules_dir into the local repository.

    Args:
        modules_dir: Directory containing v2_* module folders.
        store_full: When True, export full Docker images instead of delta archives.

    Returns:
        List of metadata dicts for modules that were synced.
    """
    synced = []
    skipped = 0

    print(f"\n🔄 Synchronisiere Module ins lokale Repository...")
    print(f"   Quelle: {modules_dir}")
    print(f"   Ziel:   {REPO_DIR}")
    print()

    for module_dir in sorted(modules_dir.glob("v2_*")):
        if not module_dir.is_dir():
            continue
        result = _sync_one_module(module_dir, modules_dir=modules_dir, store_full=store_full)
        if result is None:
            skipped += 1
        else:
            synced.append(result)

    print(f"📊 Synchronisiert: {len(synced)} | Übersprungen: {skipped}")
    return synced


def sync_single_module(module_path: Path, store_full: bool = False) -> list:
    """Sync a single module directory into the local repository.

    Unlike sync_modules(), this function ignores the modulemanager/template
    filters so any module path can be synced explicitly.

    Args:
        module_path: Absolute path to the module directory to sync.
        store_full: When True, export full Docker images instead of delta archives.

    Returns:
        List with the synced module's metadata dict, or empty list if skipped.
    """
    print(f"\n🔄 Synchronisiere einzelnes Modul...")
    print(f"   Quelle: {module_path}")
    print(f"   Ziel:   {REPO_DIR}")
    print()

    result = _sync_one_module(module_path, ignore_filters=True, store_full=store_full)
    if result is None:
        print("📊 Synchronisiert: 0 | Übersprungen: 1")
        return []
    print("📊 Synchronisiert: 1 | Übersprungen: 0")
    return [result]


def main():
    """CLI entry point for module synchronisation."""
    parser = argparse.ArgumentParser(
        description="Synchronisiert Module ins lokale Repository"
    )
    parser.add_argument(
        "modules_path",
        nargs="?",
        default=None,
        help="Pfad zum modules-Verzeichnis (Standard: ../modules)",
    )
    parser.add_argument(
        "--module",
        metavar="MODULE_PATH",
        default=None,
        help=(
            "Pfad zu einem einzelnen Modul-Verzeichnis das synchronisiert werden soll. "
            "Überspringt die modulemanager/template Filter, sodass jedes Modul "
            "explizit synchronisiert werden kann."
        ),
    )
    parser.add_argument(
        "--store-full-image",
        action="store_true",
        default=False,
        help=(
            "Export complete Docker images instead of delta archives. "
            "Delta archives (default) are smaller but require the base image "
            "to be available during installation."
        ),
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🔄 Starte Modulsynchronisation ins lokale Repository")
    print("=" * 60)

    # Sicherstellen, dass Zielverzeichnisse existieren
    (REPO_DIR / "modules").mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "plugins").mkdir(parents=True, exist_ok=True)

    if args.module:
        # Single-module mode
        module_path = Path(args.module).resolve()
        if not module_path.exists() or not module_path.is_dir():
            print(f"❌ Modul-Verzeichnis nicht gefunden: {module_path}")
            sys.exit(1)
        sync_single_module(module_path, store_full=args.store_full_image)
    else:
        # Bulk-sync mode
        if args.modules_path:
            modules_dir = Path(args.modules_path).resolve()
        else:
            modules_dir = (REPO_DIR.parent / "modules").resolve()

        if not modules_dir.exists():
            print(f"❌ Modules-Verzeichnis nicht gefunden: {modules_dir}")
            sys.exit(1)

        sync_modules(modules_dir, store_full=args.store_full_image)

    # Re-collect all available metadata — single source of truth is update_index.sh
    if (SCRIPT_DIR / "update_index.sh").exists():
        subprocess.run([SCRIPT_DIR / "update_index.sh"], check=True)
    else:
        print("❌ update_index.sh nicht gefunden — index.json wurde NICHT aktualisiert.")
        print(f"   Erwartet unter: {SCRIPT_DIR / 'update_index.sh'}")
        sys.exit(1)

    print()
    print(f"📍 Repository Pfad: {REPO_DIR}")
    print(f"🔗 Base URL: file://{REPO_DIR}")
    print("=" * 60)
    print("✅ Modulsynchronisation abgeschlossen")
    print("=" * 60)


if __name__ == "__main__":
    main()
