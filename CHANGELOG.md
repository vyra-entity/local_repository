# Changelog

## [Unreleased]

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
