# VYRA Local Repository

A self-contained, file-based module and plugin repository for offline
development. It exposes a **FastAPI HTTP server** (mirroring the
`vyra_storage_pool` API surface) and can also be consumed directly from
the file system by `v2_modulemanager` through `file://` URLs.

---

## Directory Layout

```
local_repository/
├── app/                       ← FastAPI application
│   ├── config.py
│   ├── main.py
│   ├── models.py
│   ├── storage_manager.py
│   └── routers/
│       ├── catalog.py
│       ├── files.py
│       └── health.py
├── data/                      ← Repository content root
│   ├── _registry/
│   │   └── content_types.json
│   ├── index.json             ← Unified repository index (rebuilt by update_index.sh)
│   ├── modules/
│   │   └── <name>/
│   │       └── <version>/
│   │           ├── metadata.json
│   │           ├── <name>_<version>.tar.gz
│   │           └── images/
│   │               └── <name>_<variant>.tar.gz
│   └── plugins/
│       └── <id>/
│           └── <version>/
│               ├── manifest.yaml
│               ├── schema.json      (optional)
│               ├── logic.wasm       (optional)
│               └── ui/              (optional)
├── plugins/                   ← Plugin source tree (npm-based builds)
│   └── <id>/
│       └── <version>/
│           ├── manifest.yaml
│           └── src/
├── schemas/                   ← JSON Schema definitions
│   ├── module_data.schema.json
│   └── plugin_manifest.schema.json
├── tools/
│   ├── export_module.py       ← (in VOS2_WORKSPACE/tools/) export modules
│   ├── migrate_to_data.py     ← one-time migration from legacy layout
│   ├── sync_from_modules.py   ← sync from VOS2_WORKSPACE/modules/ (CI tool)
│   ├── update_index.sh        ← rebuild data/index.json
│   ├── verify_modules.py      ← validate module packages
│   └── verify_plugins.py      ← validate plugin manifests
├── default.repository_config.json
├── requirements.txt
└── run_local.py               ← start the HTTP server
```

---

## Quick Start

### Install dependencies

```bash
pip install -r local_repository/requirements.txt
```

### Start the HTTP server

```bash
python local_repository/run_local.py
# → listening on http://0.0.0.0:8100
```

Options:

```
python run_local.py --port 8200 --host 127.0.0.1 --data-dir /data/repo --reload
```

Environment variables (prefix `VYRA_LOCAL_REPO_`):

| Variable | Default | Description |
|---|---|---|
| `VYRA_LOCAL_REPO_DATA_DIR` | `./data` | Path to the data/ directory |
| `VYRA_LOCAL_REPO_PORT` | `8100` | HTTP listening port |
| `VYRA_LOCAL_REPO_HOST` | `0.0.0.0` | Bind address |
| `VYRA_LOCAL_REPO_API_KEY` | _(empty)_ | Optional Bearer token; empty = no auth |

### File-based access (no server required)

`v2_modulemanager` can read the repository directly from the file system
without starting the HTTP server. Set the config URL to:

```json
{ "url": "file:///local_repository/data", "type": "file-based" }
```

The container_manager reads `{path}/index.json` — make sure to rebuild the
index after any changes:

```bash
bash local_repository/tools/update_index.sh
```

---

## Module Metadata (`metadata.json`)

Each module version is described by a `metadata.json` file placed alongside
the module archive.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | ✅ | Module name (`v2_*` pattern) |
| `version` | `string` | ✅ | Semantic version |
| `hash` | `string` | ✅ | 32-char hex UUID from module directory name |
| `description` | `string` | — | Short description |
| `author` | `string` | — | Author name |
| `template` | `list[string]` | — | Project templates this module belongs to |
| `icon` | `string` | — | Icon path (relative) |
| `dependencies` | `list` | — | Runtime dependencies (type + name + version) |
| `flags.frontend_active` | `bool` | — | Module provides a frontend UI |
| `flags.backend_active` | `bool` | — | Module provides a backend API |
| `filename` | `string` | — | Relative path to the tar.gz archive |
| `images` | `object` | — | Docker image entries keyed by variant |
| `synced_at` | `string` | — | ISO 8601 UTC timestamp of last export |
| `size` | `integer` | — | Archive byte size |
| `checksum` | `string` | — | SHA-256 of the archive |

### Source schema

The schema that validates `.module/module_data.yaml` (the source-of-truth
for each module) is at:

```
local_repository/schemas/module_data.schema.json
```

---

## Plugin Manifest (`manifest.yaml`)

Every plugin version directory must contain a `manifest.yaml`.
The authoritative schema is at `schemas/plugin_manifest.schema.json` (JSON Schema draft-07).

---

### Namespace ID (`id`)

Plugins use a dot-separated namespace ID:

```
<owner>.<domain>.<purpose>
```

| Situation | Format | Example |
|---|---|---|
| GLOBAL / framework plugin (no module owner) | `.global.<domain>.<purpose>` | `.global.module.system-info` |
| Module-owned plugin | `<owner_abbr>.<domain>.<purpose>` | `pm.tools.export-panel` |

**Common owner abbreviations:**

| Abbreviation | Full name |
|---|---|
| `pm` | projectmanager |
| `db` | dashboard |
| `um` | usermanager |
| `mm` | modulemanager |

**Legacy** plugins (pre-namespace) keep their kebab-case IDs like `counter-widget`.

---

### Identity & Categorization

```yaml
id: .global.module.system-info      # namespace id
name: System Info
short_description: One-liner for list views.
version: 1.0.0
author: VYRA Framework

category: infrastructure            # device-control | logic | infrastructure | analytics | visualization
sub_category: monitoring            # free-text, finer filter in Modulemanager UI
tags: [system, ui, global]

priority: 10                        # 0–100, higher = loaded first
status: development                 # development | beta | stable | deprecated
load_strategy: eager                # eager | lazy
```

---

### Scope & Owner

```yaml
scope:
  type: GLOBAL                      # GLOBAL | TEMPLATE | MODULE | INSTANCE
  owner_module: dashboard           # module that maintains this plugin
```

A plugin owned by the Project Manager targeting specific instances:

```yaml
scope:
  type: INSTANCE
  target: "project-manager-main"
  owner_module: pm                  # pm = projectmanager
```

---

### Dependencies

Tells the Container Manager what must be running before the plugin loads:

```yaml
dependencies:
  modules:
    - id: v2_dashboard
      min_version: "2.0.0"
    - id: usermanager
      min_version: "1.5.0"
  services:
    - redis     # vyra_base Redis access
    - zenoh     # Zenoh pub/sub
```

---

### Entry Points & Slot `display_options`

```yaml
entry_points:
  frontend:
    type: module
    file: plugins/sdp-system-info/1.0.0/ui/index.js
    css: []
    slots:
      - scope:
          - side-dock-popup.header
        component: SdpSystemInfoPlugin
        title: System Info
        priority: 10
        display_options:
          icon: info-circle              # icon identifier (host-module icon system)
          permissions_required:
            - view_system_info           # permission keys from RBAC
```

---

### Runtime

For plugins that need a sidecar container or backend process:

```yaml
runtime:
  image_type: SLIM    # SLIM = only ROS2 interfaces | FULL = own ROS2 nodes
  resources:
    cpu: "0.1"        # 10% of a core
    memory: "64M"
```

---

### Full Example — GLOBAL plugin

```yaml
id: .global.module.system-info
name: System Info
version: 1.0.0
category: infrastructure
sub_category: monitoring
tags: [system, ui, global]
scope:
  type: GLOBAL
  owner_module: dashboard
dependencies:
  services: [redis, zenoh]
entry_points:
  frontend:
    type: module
    file: plugins/sdp-system-info/1.0.0/ui/index.js
    css: []
    slots:
      - scope: [side-dock-popup.header]
        component: SdpSystemInfoPlugin
        display_options:
          icon: info-circle
          permissions_required: [view_system_info]
runtime:
  image_type: SLIM
  resources: {cpu: "0.1", memory: "64M"}
```

### Full Example — Module-owned plugin (projectmanager)

```yaml
id: pm.tools.export-panel           # pm = projectmanager
name: Export Panel
version: 2.1.0
category: logic
sub_category: data-export
tags: [export, project, csv, pdf]
scope:
  type: MODULE
  target: v2_projectmanager
  owner_module: pm
dependencies:
  modules:
    - id: v2_projectmanager
      min_version: "2.1.0"
  services: [redis]
entry_points:
  frontend:
    type: module
    file: plugins/pm-export-panel/2.1.0/ui/index.js
    css: []
    slots:
      - scope: [module-toolbar.right]
        component: PmExportPanel
        title: Export
        priority: 20
        display_options:
          icon: file-export
          permissions_required: [export_data, view_projects]
runtime:
  image_type: SLIM
  resources: {cpu: "0.05", memory: "32M"}
```

---

## Tools

### Export modules → export/

Creates a portable export package for each module:

```bash
# Export all modules in VOS2_WORKSPACE/modules/
python VOS2_WORKSPACE/tools/export_module.py

# Export a single module
python VOS2_WORKSPACE/tools/export_module.py --module /path/to/v2_my_module

# Export full Docker images (instead of delta archives)
python VOS2_WORKSPACE/tools/export_module.py --store-full-image

# Export and immediately import into local_repository
python VOS2_WORKSPACE/tools/export_module.py --import-to local_repository/data
```

Output: `VOS2_WORKSPACE/export/<name>/<version>/`

### Sync modules into data/

```bash
python local_repository/tools/sync_from_modules.py
```

### Rebuild index.json

```bash
bash local_repository/tools/update_index.sh
bash local_repository/tools/update_index.sh --dry-run   # preview only
```

### Validate modules

```bash
# Check data/modules/
python local_repository/tools/verify_modules.py

# Also check source modules in VOS2_WORKSPACE/modules/
python local_repository/tools/verify_modules.py --check-source
```

### Validate plugins

```bash
python local_repository/tools/verify_plugins.py

# Also check legacy plugins/ directory
python local_repository/tools/verify_plugins.py --legacy
```

### Build plugins (with schema validation)

```bash
cd local_repository/plugins
./build_all.sh

# Build a specific plugin
PLUGINS=("my-widget/1.0.0") ./build_all.sh
```

The build script runs `manifest.yaml` schema validation before every
`npm run build`. Plugins with invalid manifests are **not built**.

### Migrate from legacy layout

```bash
# Preview only (default)
python local_repository/tools/migrate_to_data.py

# Actually migrate modules/, plugins/, images/ → data/
python local_repository/tools/migrate_to_data.py --execute
```

---

## HTTP API

When the server is running (`python run_local.py`):

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/index.json` | Repository index (v2_modulemanager compat.) |
| `GET` | `/api/v1/{type}` | List all items (`modules`, `plugins`, `images`) |
| `GET` | `/api/v1/{type}/{name}` | List all versions of an item |
| `GET` | `/api/v1/{type}/{name}/{version}` | Get item metadata |
| `GET` | `/api/v1/search?q=…` | Full-text search across all types |
| `GET` | `/files/{type}/{name}/{version}/{file}` | Stream a `.tar.gz` archive |

---

## Schemas

Both schemas live in `schemas/` and use **JSON Schema draft-07**.

### `module_data.schema.json`

Validates `.module/module_data.yaml` files inside module source directories.

Required: `name` (`v2_*` pattern), `version` (semver), `uuid` (32-char hex).

### `plugin_manifest.schema.json`

Validates `manifest.yaml` files inside plugin version directories.

Required: `id` (namespace or legacy kebab-case), `name`, `version` (semver), `scope`.

New fields: `category`, `sub_category`, `tags`, `scope.owner_module`, `dependencies`, `entry_points.frontend.slots[].display_options`, `runtime`.

---

## Configuration for v2_modulemanager

To register this local repository in `v2_modulemanager`, place
`default.repository_config.json` at the expected config path or set it via
environment variable:

```json
{
  "repositories": [
    {
      "name": "local-module-repository",
      "url": "file:///local_repository/data",
      "priority": 0,
      "enabled": true,
      "type": "file-based",
      "description": "Lokales Repository für Offline-Entwicklung"
    }
  ]
}
```

For HTTP access (when `run_local.py` is running):

```json
{
  "repositories": [
    {
      "name": "local-module-repository",
      "url": "http://localhost:8100",
      "priority": 0,
      "enabled": true,
      "type": "http",
      "description": "Lokales Repository — HTTP"
    }
  ]
}
```
