# local_repository/tools

Utility scripts for managing the VYRA local module/image repository.

---

## Scripts

### `sync_from_modules.py`

Synchronises VYRA module source directories into the local repository.  
For each module it:

1. Packs the source tree into a `modules/{name}/{version}/{name}_{version}.tar.gz` archive.
2. Exports the module's Docker image(s) into `modules/{name}/{version}/images/` —  
   by default as **delta archives** (only layers added on top of `vyra_base_image`);  
   use `--store-full-image` for a complete image export.
3. Auto-detects the `vyra_base_image` version from image labels and injects a  
   `base_image` dependency entry into `metadata.json`.
4. Updates `index.json` at the repository root.

**Usage:**

```bash
# Sync all modules from the default ../modules/ directory
python tools/sync_from_modules.py

# Sync all modules from a custom directory
python tools/sync_from_modules.py /path/to/modules

# Sync a single module (bypasses modulemanager/template filters)
python tools/sync_from_modules.py --module /path/to/v2_my_module

# Export full images instead of delta archives
python tools/sync_from_modules.py --store-full-image
python tools/sync_from_modules.py --module /path/to/v2_my_module --store-full-image
```

**Delta vs. full archives:**

| Mode    | Size    | Requires base image on install | Use case                        |
|---------|---------|--------------------------------|---------------------------------|
| delta   | smaller | yes                            | default, connected deployments  |
| full    | larger  | no                             | air-gapped / offline deployment |

---

### `pack_base_image.py`

Exports local Docker base images (e.g. `vyra_base_image`, `vyra_base_image_slim`)  
as full gzip archives into `images/`.  
Archives are stored at `images/{name}/{version}/{name}_{variant}_{version}.tar.gz`.  
The `images/index.json` is updated with a minimal list of packed image entries.

**Usage:**

```bash
# Pack all known variants of vyra_base_image
python tools/pack_base_image.py vyra_base_image

# Pack a specific variant
python tools/pack_base_image.py vyra_base_image:production

# Pack with a version override
python tools/pack_base_image.py vyra_base_image --version 1.2.0

# Pack an arbitrary infrastructure image
python tools/pack_base_image.py redis:7
```

---

## Repository layout

```
local_repository/
├── index.json              ← module + plugin registry (updated by sync_from_modules.py)
├── modules/
│   └── {name}/
│       └── {version}/
│           ├── {name}_{version}.tar.gz   ← packed source archive
│           ├── metadata.json             ← module metadata + image refs + dependencies
│           └── images/
│               ├── development.tar.gz    ← dev image (delta or full)
│               ├── production.tar.gz     ← prod image (delta or full)
│               ├── slim-development.tar.gz
│               └── slim-production.tar.gz
├── images/
│   ├── index.json          ← image list (stateless, no repo metadata)
│   └── {name}/
│       └── {version}/
│           └── {name}_{variant}_{version}.tar.gz
├── plugins/
│   └── {name}/{version}/
└── tools/
    ├── README.md           ← this file
    ├── sync_from_modules.py
    └── pack_base_image.py
```

## Image archive formats

### Delta archive (`base_info.json` present inside tar)

Contains only the layers added by the module on top of the base image.  
Includes the full `manifest.json` and image config so the `container_manager`  
can reconstruct a loadable image by merging with the locally available base image.

### Full archive (no `base_info.json`)

A standard `docker save | gzip` export.  
Can be loaded directly with `docker load`.
