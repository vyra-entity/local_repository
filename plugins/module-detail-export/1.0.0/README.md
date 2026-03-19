# module-detail-export Plugin

**Version:** 1.0.0  
**Scope:** `MODULE → v2_modulemanager`  
**Slot:** `module.detail.actions`

## Overview

Adds a small xlsx download button (⬇) to every tab panel in the v2_modulemanager **Module Details** dialog. Clicking the button exports the currently displayed data as an `.xlsx` file using [SheetJS](https://sheetjs.com/) (loaded from CDN on first use — no bundling required).

## Tabs and Export Content

| Tab | Sheet Name | Exported Columns |
|---|---|---|
| Info | Info | Key, Value |
| Functions | Functions | Function Name, Type, Description, Arguments |
| Parameters | Params | Key, Display Name, Value, Default, Type, Description |
| Volatile | Volatile | Key, Value |
| Feeds | State Feeds / Error Feeds / News Feeds | Timestamp, State, Data, Description |
| Logs | Logs | Timestamp, Level, Logger, Message |

## Installation

1. Ensure the plugin files are present in the local repository under:
   ```
   /local_repository/plugins/module-detail-export/1.0.0/
   ```

2. Open **v2_modulemanager → Repository → Plugins** and install `Module Detail Export`.

3. Reload the page. The download button will appear in each tab of the module details dialog.

## Props

The host injects the following props via `<PluginSlot>`:

| Prop | Type | Description |
|---|---|---|
| `tab` | `string` | Active tab key (`info`, `functions`, `params`, `volatile`, `feeds`, `logs`) |
| `instanceId` | `string` | Module instance ID, used in the filename |
| `moduleData` | `object` | Tab-specific data snapshot (see below) |

### `moduleData` Shape per Tab

```js
// info
{ info: { module_name, instance_id, version, author, state, ...detailState } }

// functions
{ functions: [ { name, type, description, args } ] }

// params
{ params: { paramKey: { display_name, value, default_value, type, description } } }

// volatile
{ volatiles: { key: value } }

// feeds
{ stateFeeds: [...], errorFeeds: [...], newsFeeds: [...] }

// logs
{ logLines: [ { ts, level, logger, message } ] }
```

## Network Access

SheetJS is loaded from `https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs` on the first download click. Subsequent calls reuse the cached module. The `network: true` permission in the manifest reflects this.

## Development Notes

- No backend WASM module required.
- Signature verification is skipped (development status).
- Checksum is empty — no file verification needed.
