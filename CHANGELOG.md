# Changelog

## [Unreleased]

### Changed — Plugin manifest schema: namespace ID, category, dependencies, runtime (2026-04-16)

- **`data/plugins/sdp-system-info/1.0.0/manifest.yaml`**: Extended with new fields:
  - `id` changed to namespace format `.global.module.system-info`
  - `category: infrastructure`, `sub_category: monitoring`, `tags: [system, ui, global]`
  - `scope.owner_module: dashboard`
  - `dependencies.modules` (v2_dashboard ≥2.0.0, usermanager ≥1.5.0) and `dependencies.services` (redis, zenoh)
  - `entry_points.frontend.slots[].display_options` with `icon` and `permissions_required`
  - `runtime` block with `image_type: SLIM` and resource limits
- **`schemas/plugin_manifest.schema.json`**: Added schema support for all new fields:
  - `id` pattern updated to support namespace format (`<owner>.<domain>.<purpose>`, leading dot for GLOBAL)
  - New top-level properties: `category` (enum), `sub_category`, `tags`
  - `scope.owner_module` field
  - `dependencies` object with `modules[]` (id + min_version) and `services[]`
  - `entry_points.frontend.slots[].display_options` with `icon` and `permissions_required`
  - `runtime` object with `image_type` (SLIM/FULL) and `resources` (cpu, memory)
  - Slot item `required` updated from `["id", "component"]` → `["scope", "component"]` (matches the April 2026 scope-list migration); `id` kept as deprecated optional field
- **`README.md`**: Plugin Manifest section fully expanded inline with:
  - Namespace ID format explanation and owner abbreviation table
  - Per-section YAML examples (identity, scope, dependencies, entry_points, runtime)
  - Full examples for a GLOBAL plugin and a module-owned `pm.*` plugin



- **`app/`**: New FastAPI application (mirrors vyra_storage_pool architecture).
  - `app/config.py`: Pydantic-Settings config with env prefix `VYRA_LOCAL_REPO_`.
  - `app/storage_manager.py`: Async file-based CRUD for modules, plugins, images.
  - `app/models.py`: Pydantic response models.
  - `app/routers/health.py`, `catalog.py`, `files.py`: HTTP endpoints.
  - `app/main.py`: FastAPI app with CORS and lifespan bootstrap.
- **`run_local.py`**: CLI entrypoint — `python run_local.py [--port 8100]`.
- **`requirements.txt`**: fastapi, uvicorn, pydantic-settings, aiofiles, pyyaml, jsonschema.
- **`data/_registry/content_types.json`**: Registry of supported content types.

### Added — JSON Schema definitions

- **`schemas/plugin_manifest.schema.json`**: JSON Schema draft-07 for `manifest.yaml` files.
- **`schemas/module_data.schema.json`**: JSON Schema draft-07 for `.module/module_data.yaml` files.

### Added — Module export script

- **`VOS2_WORKSPACE/tools/export_module.py`**: Exports one or all modules from
  `VOS2_WORKSPACE/modules/` into `VOS2_WORKSPACE/export/<name>/<version>/` with
  `metadata.json`, source archive, and Docker image layers (delta or full).
  Supports `--module`, `--store-full-image`, `--force`, `--import-to`.

### Added — Verify tools

- **`tools/verify_modules.py`**: Validates module packages against `schemas/module_data.schema.json`.
  Supports `--check-source` to also verify `.module/module_data.yaml` in workspace modules.
- **`tools/verify_plugins.py`**: Validates plugin manifests against `schemas/plugin_manifest.schema.json`.
  Supports `--legacy` to also check the legacy `plugins/` directory.

### Added — Migration script

- **`tools/migrate_to_data.py`**: Migrates legacy `modules/`, `plugins/`, `images/`, `index.json`
  into the new `data/` subdirectory layout. Dry-run by default; use `--execute` to apply.

### Changed — build_all.sh: schema validation before npm build

- **`plugins/build_all.sh`**: Added `_validate_manifest()` function that runs `manifest.yaml`
  against `schemas/plugin_manifest.schema.json` before every `npm run build`.
  Plugins with invalid manifests are skipped and reported as failed.

### Changed — data/ layout as new repository root

- **`default.repository_config.json`**: URL updated from `file:///local_repository` to
  `file:///local_repository/data`.
- **`tools/update_index.sh`**: Now reads/writes `data/index.json`, `data/modules/`, `data/plugins/`
  when `data/` exists; falls back to root-level dirs for legacy compatibility.
- **`tools/sync_from_modules.py`**: Now writes to `data/modules/` when `data/` exists.

### Changed — Plugin manifest slot schema migration (2026-04-01)

- **All plugin `manifest.yaml` files**: Migrated slot entries from legacy `id: "slot-name"` string format to new `scope: ["slot-name"]` list format. This enables a single component to target multiple slots.
- **Slot-level module filter**: Renamed from `scope: {type:, target:}` to `slot_scope: {type:, target:}` to avoid ambiguity with the new `scope:` list field.
- Affected files: `counter-widget/1.0.0/manifest.yaml`, `module-detail-export/1.0.3/manifest.yaml`, `module-detail-export/1.1.0/manifest.yaml`, `zenoh-log-exporter/1.0.2/manifest.yaml`, `module-count-widget/1.0.0/manifest.yaml`.

- Published UserManager module to local repository via `sync_from_modules.py --module`.
- Source archive: `modules/usermanager/1.0.0/usermanager_1.0.0.tar.gz` (2.1 MB).
- Metadata includes: RBAC, JWT RS256 auth, SQLite backend, Vue 3 / PrimeVue frontend, 15 Zenoh interfaces.
- Docker images not yet built (metadata written without images block).

### Added — remove_module.sh and remove_plugin.sh (2026-03-30)

- **`tools/remove_module.sh`**: New script to remove a module (all versions or a specific version) from the local repository and automatically rebuild `index.json`.
- **`tools/remove_plugin.sh`**: New script to remove a plugin (all versions or a specific version) from the local repository and automatically rebuild `index.json`.

### Fixed — module-detail-export 1.1.0: bare "vue" specifier error (2026-03-27)

- **`plugins/module-detail-export/1.1.0/src/vite.config.ts`**: Removed `external: ['vue']` and `globals: { vue: 'Vue' }` from `rollupOptions`. Vue is now bundled into `ui/index.js`, making the plugin fully self-contained. Fixes `TypeError: The specifier "vue" was a bare specifier, but was not remapped to anything` that occurred because `globals` has no effect for `format: 'es'` builds.
- **`plugins/build_all.sh`**: Updated `module-detail-export` entry from `1.0.3` to `1.1.0`.
- **`plugins/module-detail-export/1.1.0/ui/index.js`**: Rebuilt (54.7 kB, self-contained).

### Fixed — sync_from_modules.py: metadata.json auch ohne Docker-Images schreiben (2026-03-25)

- `_sync_one_module`: Bei fehlendem lokalen Docker-Image (`RuntimeError`) wurde bisher mit
  `return None` abgebrochen und `metadata.json` nie geschrieben. Jetzt wird die Warnung
  ausgegeben und `metadata.json` ohne `images`-Einträge geschrieben.
- Skip-Logik ("kein Update" / "identisch") prüft jetzt zusätzlich ob `metadata.json`
  existiert. Fehlt sie, wird das Modul immer vollständig synchronisiert — auch wenn das
  tar.gz noch aktuell ist.
