<template>
  <span class="vyra-detail-export">
    <button
      class="vyra-detail-export__btn"
      :disabled="loading"
      :title="`Download ${tabLabel} as xlsx`"
      @click="download"
    >
      <span v-if="loading" class="vyra-detail-export__spinner">⏳</span>
      <span v-else class="vyra-detail-export__icon">⬇(.xlsx)</span>
    </button>
    <span v-if="error" class="vyra-detail-export__error" :title="error">⚠</span>
  </span>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

// CDN URL for SheetJS 0.20 (ESM build) — loaded lazily on first click
const XLSX_CDN = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs'

const props = withDefaults(defineProps<{
  /** Current detail tab */
  tab?: string
  /** Module instance ID (first 4 chars used in filename) */
  instanceId?: string
  /** Module name (used as prefix in filename) */
  moduleName?: string
  /** Tab-specific data snapshot provided by the host */
  moduleData?: Record<string, any>
}>(), {
  tab: 'info',
  instanceId: '',
  moduleName: 'module',
  moduleData: () => ({}),
})

const loading = ref(false)
const error   = ref<string | null>(null)

const tabLabel = computed(() => {
  const labels: Record<string, string> = {
    info:      'Info',
    functions: 'Functions',
    params:    'Parameters',
    volatile:  'Volatile',
    feeds:     'Feeds',
    logs:      'Logs',
  }
  return labels[props.tab] ?? props.tab
})

// ── Style injection ───────────────────────────────────────────────────────────

let _stylesInjected = false
function injectStyles() {
  if (_stylesInjected) return
  _stylesInjected = true
  const style = document.createElement('style')
  style.textContent = `
    .vyra-detail-export {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .vyra-detail-export__btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 55px;
      height: 28px;
      padding: 0;
      border: 1px solid var(--p-surface-border, #3d4a5c);
      border-radius: 4px;
      background: transparent;
      color: var(--p-text-color, #ced4da);
      cursor: pointer;
      font-size: 14px;
      transition: background 0.15s, border-color 0.15s;
    }
    .vyra-detail-export__btn:hover:not(:disabled) {
      background: var(--p-surface-hover, #2a3547);
      border-color: var(--p-primary-color, #6c9aff);
      color: var(--p-primary-color, #6c9aff);
    }
    .vyra-detail-export__btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .vyra-detail-export__error {
      color: var(--p-red-400, #f87171);
      font-size: 13px;
    }
  `
  document.head.appendChild(style)
}

onMounted(injectStyles)

// ── SheetJS lazy loader ───────────────────────────────────────────────────────

let _xlsxPromise: Promise<any> | null = null

function loadXlsx(): Promise<any> {
  if (!_xlsxPromise) {
    _xlsxPromise = import(/* @vite-ignore */ XLSX_CDN).catch(err => {
      _xlsxPromise = null
      throw err
    })
  }
  return _xlsxPromise
}

// ── Row builders ─────────────────────────────────────────────────────────────

function buildInfoRows(data: any, instanceId: string) {
  const info = data.info ?? {}
  const rows: any[] = []
  for (const [key, value] of Object.entries(info)) {
    rows.push({ Key: key, Value: value == null ? '' : String(value) })
  }
  if (rows.length === 0 && instanceId) rows.push({ Key: 'instance_id', Value: instanceId })
  return rows
}

function buildFunctionsRows(data: any) {
  const fns = data.functions ?? []
  return fns.map((fn: any) => {
    const formatFields = (arr: any[]) =>
      (arr ?? []).map(f => `${f.name ?? f.displayname ?? ''}: ${f.datatype ?? ''}`).join(', ')
    return {
      'Function Name': fn.functionname ?? fn.function_name ?? fn.name ?? '',
      'Display Name':  fn.displayname ?? '',
      Type:            fn.type ?? '',
      Description:     fn.description ?? '',
      'Request IN':    formatFields(fn.params),
      'Response OUT':  formatFields(fn.returns),
    }
  })
}

function buildParamsRows(data: any) {
  const params = data.params ?? {}
  return Object.entries(params).map(([key, p]: [string, any]) => ({
    Key:            key,
    'Display Name': p?.display_name ?? p?.displayname ?? '',
    Value:          p?.value == null ? '' : String(p.value),
    Default:        p?.default_value == null ? '' : String(p.default_value),
    Type:           p?.type ?? '',
    Description:    p?.description ?? '',
  }))
}

function buildVolatileRows(data: any) {
  const vols = data.volatiles ?? {}
  return Object.entries(vols).map(([key, v]: [string, any]) => ({
    Key:   key,
    Value: v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v),
  }))
}

function buildFeedsSheets(data: any) {
  const mapRows = (arr: any[]) => (arr ?? []).map(f => ({
    Timestamp:   f.ts ?? f.timestamp ?? '',
    State:       f.state ?? '',
    Data:        f.data == null ? '' : typeof f.data === 'object' ? JSON.stringify(f.data) : String(f.data),
    Description: f.description ?? '',
  }))
  return [
    { name: 'State Feeds', rows: mapRows(data.stateFeeds) },
    { name: 'Error Feeds', rows: mapRows(data.errorFeeds) },
    { name: 'News Feeds',  rows: mapRows(data.newsFeeds)  },
  ]
}

function buildLogsRows(data: any) {
  const lines = data.logLines ?? []
  return lines.map((l: any) => ({
    Timestamp: l.ts ?? '',
    Level:     l.level ?? '',
    Logger:    l.logger ?? '',
    Message:   l.message ?? '',
  }))
}

// ── Download ─────────────────────────────────────────────────────────────────

function triggerDownload(data: Uint8Array | ArrayBuffer, filename: string) {
  const blob = new Blob([data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href     = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url) }, 100)
}

function generateXlsx(XLSX: any) {
  const wb = XLSX.utils.book_new()
  const safeModule = (props.moduleName ?? 'module').replace(/[^a-z0-9_-]/gi, '_').slice(0, 24)
  const shortId    = (props.instanceId ?? '').slice(0, 4) || 'mod'
  const filename   = `${safeModule}_${shortId}_${props.tab}_${new Date().toISOString().slice(0, 10)}.xlsx`

  if (props.tab === 'feeds') {
    for (const { name, rows } of buildFeedsSheets(props.moduleData)) {
      const ws = rows.length > 0 ? XLSX.utils.json_to_sheet(rows) : XLSX.utils.aoa_to_sheet([['No data']])
      XLSX.utils.book_append_sheet(wb, ws, name)
    }
  } else {
    let rows: any[]
    switch (props.tab) {
      case 'info':      rows = buildInfoRows(props.moduleData, props.instanceId);  break
      case 'functions': rows = buildFunctionsRows(props.moduleData);               break
      case 'params':    rows = buildParamsRows(props.moduleData);                  break
      case 'volatile':  rows = buildVolatileRows(props.moduleData);                break
      case 'logs':      rows = buildLogsRows(props.moduleData);                    break
      default:          rows = []
    }
    const ws = rows.length > 0 ? XLSX.utils.json_to_sheet(rows) : XLSX.utils.aoa_to_sheet([['No data']])
    XLSX.utils.book_append_sheet(wb, ws, props.tab.charAt(0).toUpperCase() + props.tab.slice(1))
  }

  const wbOut = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
  triggerDownload(wbOut, filename)
}

async function download() {
  if (loading.value) return
  loading.value = true
  error.value   = null
  try {
    const XLSX = await loadXlsx()
    generateXlsx(XLSX)
  } catch (e: any) {
    console.error('[module-detail-export] download error:', e)
    error.value = 'Export failed'
  } finally {
    loading.value = false
  }
}
</script>
