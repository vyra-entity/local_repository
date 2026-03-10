# VYRA Plugin System — manifest.yaml Schema Reference

A VYRA plugin is described by a `manifest.yaml` file that lives in the
plugin's versioned directory inside `local_repository/plugins/`:

```
local_repository/plugins/
└── <plugin-id>/
    └── <version>/
        ├── manifest.yaml        ← this schema
        ├── schema.json          ← optional: JSON Schema for config_overlay
        ├── logic.wasm           ← backend WASM module
        └── ui/
            ├── index.js         ← ES module entry point (Vue 3 SFC compiled)
            └── style.css
```

---

## Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | ✅ | Unique identifier (kebab-case). Stored as `plugin_name_id` in the DB. |
| `name` | `string` | ✅ | Human-readable display name. |
| `version` | `string` | ✅ | Semantic version (`MAJOR.MINOR.PATCH`). |
| `author` | `string` | — | Author or organisation. |
| `description` | `string` | — | Short description shown in the plugin list UI. |
| `priority` | `integer` | — | Global load priority 0–100 (higher = loaded first). Default: `50`. |
| `status` | `string` | — | `development` \| `beta` \| `stable` \| `deprecated`. |
| `load_strategy` | `string` | — | `eager` (load at startup) \| `lazy` (load on first access). |
| `compatible_with` | `list[string]` | — | Module `name_id`s this plugin targets. |
| `config_schema` | `string\|null` | — | Path to `schema.json` relative to NFS pool root. `null` if no config. |
| `hash` | `string` | — | Composite identifier for DB deduplication. |
| `checksum` | `string` | — | SHA-256 of the packaged archive (set by build pipeline). |

---

## `scope`

Defines where the plugin is available.

```yaml
scope:
  type: MODULE          # GLOBAL | TEMPLATE | MODULE | INSTANCE
  target: v2_dashboard  # scope target; ignored for GLOBAL
```

| `type` | `target` meaning |
|---|---|
| `GLOBAL` | Available everywhere; `target` is ignored. |
| `TEMPLATE` | Available on all modules using a named project template (e.g. `welding_cell`). |
| `MODULE` | Available on all instances of a specific module (e.g. `v2_dashboard`). |
| `INSTANCE` | Available on one specific module instance (e.g. `v2_dashboard_<uuid>`). |

---

## `permissions`

```yaml
permissions:
  interfaces: []          # List of allowed VYRA transport interface names
  network: false          # true → plugin may make outbound HTTP/TCP calls
  storage: none           # none | read-only | read-write
  zenoh_scopes:           # optional: Zenoh key-expression scopes allowed
    - myproject/logs/**
```

---

## `entry_points.backend`

```yaml
entry_points:
  backend:
    type: wasm
    file: plugins/<id>/<version>/logic.wasm   # relative to NFS pool root
    handler: init           # WASM export called at startup
    runtime_limits:
      memory_mb: 16
      cpu_shares: 0.05
    exports:
      - name: my_function
        args:
          - name: value
            type: i32       # WASM numeric type: i32 | i64 | f32 | f64
```

`exports` drives the `WasmRuntime` dispatch: each `args` entry maps
positionally to a WASM i32 parameter. The **order** in `args` determines
the WASM call argument order, not the key names in the `data` dict.

---

## `entry_points.frontend`

```yaml
entry_points:
  frontend:
    type: module
    file: plugins/<id>/<version>/ui/index.js   # ES module
    css:
      - plugins/<id>/<version>/ui/style.css
    slots:
      - id: home-widget           # slot_id defined by the host module
        component: MyComponent    # Vue 3 component name exported from index.js
        title: My Widget
        priority: 10              # slot-level rendering priority
        min_width: 1              # dashboard grid columns (optional)
        min_height: 1             # dashboard grid rows (optional)
```

Slot IDs are defined by the host module (e.g. `v2_dashboard`). The
`component` value must match the named export from `ui/index.js`.

---

## `schema.json` (plugin config schema)

If `config_schema` is set, the referenced JSON Schema (draft-07) is used
to validate the `config_overlay` supplied on plugin installation.

```jsonc
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "My Plugin Config",
  "type": "object",
  "properties": {
    "my_option": { "type": "integer", "default": 0 }
  },
  "additionalProperties": false
}
```

---

## `docs`

```yaml
docs:
  wiki_path: plugins/<id>/<version>/    # path to documentation inside the plugin directory
  search_keywords:
    - keyword1
    - keyword2
```
