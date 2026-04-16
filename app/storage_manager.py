"""Storage manager — reads content types and items directly from the data/ directory.

Directory layout (mirrors vyra_storage_pool):
  data/
    _registry/
      content_types.json        — registered content types
    index.json                  — unified index (modules + plugins + images)
    modules/<name>/<version>/
      metadata.json
      <name>_<version>.tar.gz
      images/<name>_<variant>.tar.gz
    plugins/<name>/<version>/
      manifest.yaml
      ...
    images/<name>/<version>/
      ...
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import aiofiles

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StorageManager:
    """Manages all content types inside the local data directory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── Content type registry ─────────────────────────────────────────────────

    def get_content_types(self) -> list[str]:
        """Return the list of registered content types.

        Falls back to ["modules", "plugins", "images"] if the registry file
        is missing or malformed.
        """
        path = self._settings.registry_file
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return ["modules", "plugins", "images"]

    def register_content_type(self, name: str) -> bool:
        """Register a new content type if not already present.

        Creates the type directory and updates content_types.json.
        Returns True if the type was newly registered, False if it already existed.
        """
        types = self.get_content_types()
        if name in types:
            return False
        types.append(name)
        path = self._settings.registry_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(types), indent=2) + "\n")
        type_dir = self._settings.data_dir / name
        type_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Registered new content type: %s", name)
        return True

    def _validate_content_type(self, content_type: str) -> None:
        """Raise ValueError if *content_type* is not registered."""
        if content_type not in self.get_content_types():
            raise ValueError(f"Unknown content type: '{content_type}'")

    # ── Index access ──────────────────────────────────────────────────────────

    def get_index(self) -> dict:
        """Return the parsed unified index.json, or an empty skeleton."""
        path = self._settings.index_file
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "name": "local-repository",
                "description": "VYRA Local Repository for offline development",
                "version": "1.0.0",
                "type": "file-based",
                "base_url": f"http://{self._settings.domain}:{self._settings.port}",
                "last_updated": _now_utc(),
                "modules": [],
                "plugins": [],
                "images": [],
            }

    def get_items_for_type(self, content_type: str) -> list[dict]:
        """Return all index entries for *content_type*."""
        self._validate_content_type(content_type)
        index = self.get_index()
        return index.get(content_type, [])

    def get_item_versions(self, content_type: str, name: str) -> list[dict]:
        """Return all version entries for *name* within *content_type*."""
        self._validate_content_type(content_type)
        items = self.get_items_for_type(content_type)
        return [
            item for item in items
            if item.get("name") == name or item.get("id") == name
        ]

    def get_item_metadata(
        self, content_type: str, name: str, version: str
    ) -> dict | None:
        """Return the metadata dict for one specific version, or None."""
        self._validate_content_type(content_type)
        version_dir = self._settings.data_dir / content_type / name / version
        # Modules use metadata.json, plugins use manifest.yaml
        meta_json = version_dir / "metadata.json"
        if meta_json.exists():
            try:
                return json.loads(meta_json.read_text())
            except json.JSONDecodeError:
                logger.warning("Malformed metadata.json at %s", meta_json)
                return None
        manifest_yaml = version_dir / "manifest.yaml"
        if manifest_yaml.exists():
            try:
                import yaml  # lazy import

                return yaml.safe_load(manifest_yaml.read_text()) or {}
            except Exception as exc:
                logger.warning("Failed to read manifest.yaml at %s: %s", manifest_yaml, exc)
                return None
        return None

    def search_items(self, query: str) -> list[dict]:
        """Return items whose name or description contains *query* (case-insensitive)."""
        q = query.lower()
        results = []
        for ctype in self.get_content_types():
            for item in self.get_items_for_type(ctype):
                name = str(item.get("name") or item.get("id") or "").lower()
                desc = str(item.get("description") or "").lower()
                if q in name or q in desc:
                    results.append({"content_type": ctype, **item})
        return results

    # ── File streaming ────────────────────────────────────────────────────────

    async def stream_file(
        self,
        content_type: str,
        name: str,
        version: str,
        filename: str,
    ) -> AsyncGenerator[bytes, None]:
        """Yield file chunks from the data directory.

        Only .tar.gz and .sha256 filenames are allowed.

        Raises:
            ValueError: If the filename extension is not allowed.
            FileNotFoundError: If the file does not exist.
        """
        if not (filename.endswith(".tar.gz") or filename.endswith(".sha256")):
            raise ValueError(f"File type not allowed: {filename!r}")
        path = self._settings.data_dir / content_type / name / version / filename
        if not path.exists():
            raise FileNotFoundError(path)
        async with aiofiles.open(path, "rb") as fh:
            while True:
                chunk = await fh.read(65536)
                if not chunk:
                    break
                yield chunk

    # ── Import helpers ────────────────────────────────────────────────────────

    def import_from_export(self, export_dir: Path) -> dict | None:
        """Import a module or plugin from an export directory into data/.

        The export directory must contain a metadata.json or manifest.yaml.
        Files are copied into data/<content_type>/<name>/<version>/ and the
        index.json is updated.

        Returns the metadata dict on success, or None on failure.
        """
        import shutil

        meta: dict | None = None
        content_type: str = "modules"

        # Try metadata.json first (modules), then manifest.yaml (plugins)
        meta_json = export_dir / "metadata.json"
        manifest_yaml = export_dir / "manifest.yaml"

        if meta_json.exists():
            try:
                meta = json.loads(meta_json.read_text())
                content_type = "modules"
            except json.JSONDecodeError:
                logger.error("Malformed metadata.json in %s", export_dir)
                return None
        elif manifest_yaml.exists():
            try:
                import yaml

                meta = yaml.safe_load(manifest_yaml.read_text()) or {}
                content_type = "plugins"
            except Exception as exc:
                logger.error("Failed to read manifest.yaml in %s: %s", export_dir, exc)
                return None
        else:
            logger.error("No metadata.json or manifest.yaml found in %s", export_dir)
            return None

        name = meta.get("name") or meta.get("id") or ""
        version = meta.get("version") or ""
        if not name or not version:
            logger.error("Metadata missing name or version in %s", export_dir)
            return None

        dest_dir = self._settings.data_dir / content_type / name / version
        dest_dir.mkdir(parents=True, exist_ok=True)

        for src in export_dir.iterdir():
            dst = dest_dir / src.name
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

        logger.info("Imported %s/%s/%s into data/", content_type, name, version)
        return meta


def get_storage_manager() -> StorageManager:
    """FastAPI dependency that returns a StorageManager instance."""
    return StorageManager(get_settings())
