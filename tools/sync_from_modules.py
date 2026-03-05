#!/usr/bin/env python3
"""
sync_from_modules.py
Synchronisiert Module aus dem /modules Ordner in das lokale Repository.

Neue Struktur:
  modules/{module_name}/{version}/metadata.json
  modules/{module_name}/{version}/{module_name}_{version}.tar.gz
  plugins/
  index.json

Verwendung:
  python3 tools/sync_from_modules.py [PFAD_ZU_MODULES]
"""

import argparse
import hashlib
import json
import os
import re
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
            elif line == "ENABLE_BACKEND_API=true":
                flags["backend_active"] = True
    return flags


def strip_uuid_suffix(name: str) -> str:
    """Entferne UUID-Suffix aus Modulname, z.B. v2_dashboard_aef036f... → v2_dashboard."""
    return re.sub(r"_[a-f0-9]{32}$", "", name)


def get_uuid_suffix(name: str) -> str:
    """Extrahiere UUID-Suffix aus Modulname."""
    match = re.search(r"([a-f0-9]{32})$", name)
    return match.group(1) if match else ""


def sync_modules(modules_dir: Path) -> list:
    """Synchronisiert alle Module und gibt eine Liste der Metadaten zurück."""
    synced = []
    skipped = 0

    print(f"\n🔄 Synchronisiere Module ins lokale Repository...")
    print(f"   Quelle: {modules_dir}")
    print(f"   Ziel:   {REPO_DIR}")
    print()

    for module_dir in sorted(modules_dir.glob("v2_*")):
        if not module_dir.is_dir():
            continue

        dir_name = module_dir.name

        # Modulemanager überspringen
        if "modulemanager" in dir_name:
            print(f"⏭️  Überspringe Modulemanager: {dir_name}")
            continue

        # Lese Metadaten
        data = read_module_data(module_dir)
        if not data:
            print(f"⚠️  Keine module_data.yaml gefunden: {dir_name}")
            continue

        name = data.get("name") or strip_uuid_suffix(dir_name)

        # Template-Module überspringen
        if "template" in name:
            print(f"⏭️  Überspringe Template-Modul: {name}")
            continue

        version = data.get("version", "0.0.0")
        description = str(data.get("description") or "").replace("\n", " ").strip()
        author = str(data.get("author") or "")
        template = str(data.get("template") or "basic")
        icon = str(data.get("icon") or "")
        dependencies = data.get("dependencies") or []
        version_hash = get_uuid_suffix(dir_name)
        flags = read_module_flags(module_dir)

        # Zielverzeichnis: modules/{name}/{version}/
        version_dir = REPO_DIR / "modules" / name / version
        version_dir.mkdir(parents=True, exist_ok=True)

        archive_name = f"{name}_{version}.tar.gz"
        archive_path = version_dir / archive_name
        relative_filename = f"modules/{name}/{version}/{archive_name}"

        # Prüfe ob Archiv bereits vorhanden ist (Quelle als vorgefertigte .tar.gz)
        prebuilt = modules_dir / archive_name
        if prebuilt.exists():
            print(f"📦 Gefunden (vorgebaut): {archive_name}")
            tar_source = prebuilt
            use_copy = True
        else:
            print(f"📦 Packe: {dir_name}")
            print(f"   - 📁 Quelle: {module_dir}")
            tar_source = None
            use_copy = False

        if use_copy:
            if archive_path.exists() and archive_path.stat().st_size == prebuilt.stat().st_size:
                print(f"   - ⏭️  Überspringe (identisch)")
                skipped += 1
                continue
            import shutil
            shutil.copy2(prebuilt, archive_path)
        else:
            if archive_path.exists():
                # Einfacher Zeitstempel-Vergleich als Änderungscheck
                mod_time = max(
                    (f.stat().st_mtime for f in module_dir.rglob("*") if f.is_file()),
                    default=0
                )
                if archive_path.stat().st_mtime >= mod_time:
                    print(f"   - ⏭️  Überspringe (kein Update)")
                    skipped += 1
                    continue
                print(f"   - ♻️  Update (Modul hat sich geändert)")
            pack_module(module_dir, archive_path)
            print(f"   - ✅ Packen erfolgreich")

        checksum = sha256_file(archive_path)
        size = archive_path.stat().st_size
        synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Schreibe metadata.json in das Versionsverzeichnis
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
            "synced_at": synced_at,
            "size": size,
            "checksum": checksum,
        }

        metadata_path = version_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"   - ✅ Synchronisiert: {name} v{version}")
        print()
        synced.append(metadata)

    print(f"📊 Synchronisiert: {len(synced)} | Übersprungen: {skipped}")
    return synced


def collect_all_modules() -> list:
    """Lese alle metadata.json aus modules/{name}/{version}/ Verzeichnissen."""
    modules = []
    modules_dir = REPO_DIR / "modules"
    if not modules_dir.exists():
        return modules
    for name_dir in sorted(modules_dir.iterdir()):
        if not name_dir.is_dir():
            continue
        for version_dir in sorted(name_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            meta_file = version_dir / "metadata.json"
            if meta_file.exists():
                with open(meta_file, "r") as f:
                    modules.append(json.load(f))
    return modules


def collect_all_plugins() -> list:
    """
    Lese alle plugins/{name}/{version}/metadata.json Verzeichnisse.

    Erwartet folgende Pflichtfelder (neue Schema-Version):
      name, version, type, description, priority, status,
      compatibility, load_strategy, permissions, entry_points,
      dependencies, filename, hash, checksum
    """
    plugins = []
    plugins_dir = REPO_DIR / "plugins"
    if not plugins_dir.exists():
        return plugins
    for name_dir in sorted(plugins_dir.iterdir()):
        if not name_dir.is_dir():
            continue
        for version_dir in sorted(name_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            meta_file = version_dir / "metadata.json"
            if meta_file.exists():
                with open(meta_file, "r") as f:
                    plugins.append(json.load(f))
    return plugins


def update_index(modules: list, plugins: list) -> None:
    """Aktualisiert index.json mit der aktuellen Modul- und Plugin-Liste."""
    index_path = REPO_DIR / "index.json"

    index = {
        "name": "local-module-repository",
        "description": "Lokales Vyra Module Repository für Offline-Entwicklung",
        "version": "1.0.0",
        "type": "file-based",
        "base_url": "file:///local_repository",
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "modules": modules,
        "plugins": plugins,
    }

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n📝 index.json aktualisiert ({len(modules)} Module, {len(plugins)} Plugins)")


def main():
    parser = argparse.ArgumentParser(
        description="Synchronisiert Module ins lokale Repository"
    )
    parser.add_argument(
        "modules_path",
        nargs="?",
        default=None,
        help="Pfad zum modules-Verzeichnis (Standard: ../modules)",
    )
    args = parser.parse_args()

    if args.modules_path:
        modules_dir = Path(args.modules_path).resolve()
    else:
        modules_dir = (REPO_DIR.parent / "modules").resolve()

    print("=" * 60)
    print("🔄 Starte Modulsynchronisation ins lokale Repository")
    print("=" * 60)

    if not modules_dir.exists():
        print(f"❌ Modules-Verzeichnis nicht gefunden: {modules_dir}")
        sys.exit(1)

    # Sicherstellen, dass Zielverzeichnisse existieren
    (REPO_DIR / "modules").mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "plugins").mkdir(parents=True, exist_ok=True)

    # Module synchronisieren
    sync_modules(modules_dir)

    # Alle verfügbaren Metadaten einlesen (inkl. bereits vorhandene)
    all_modules = collect_all_modules()
    all_plugins = collect_all_plugins()

    # index.json aktualisieren
    update_index(all_modules, all_plugins)

    print()
    print(f"📍 Repository Pfad: {REPO_DIR}")
    print(f"🔗 Base URL: file://{REPO_DIR}")
    print("=" * 60)
    print("✅ Modulsynchronisation abgeschlossen")
    print("=" * 60)


if __name__ == "__main__":
    main()
