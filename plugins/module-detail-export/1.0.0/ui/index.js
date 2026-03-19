/**
 * ModuleDetailExport — VYRA Plugin
 * Scope: v2_modulemanager / Slot: module.detail.actions
 *
 * Renders a small xlsx download button. The host (ModulesView.vue) passes
 * component props:
 *
 *   tab        {string}  — active tab key: 'info' | 'functions' | 'params' |
 *                          'volatile' | 'feeds' | 'logs'
 *   instanceId {string}  — module instance ID (used in filename)
 *   moduleData {object}  — tab-specific data snapshot:
 *     info:     { module_name, instance_id, version, author, ...detailState }
 *     functions:{ functions: Array }
 *     params:   { params: Object }
 *     volatile: { volatiles: Object }
 *     feeds:    { stateFeeds, errorFeeds, newsFeeds }
 *     logs:     { logLines: Array<{ts, level, message, logger}> }
 *
 * SheetJS is loaded lazily from CDN on first use to keep the bundle small.
 */

const { defineComponent, ref, computed } = window.Vue;

// CDN URL for SheetJS 0.20 (ESM build)
const XLSX_CDN = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs';

let _xlsxPromise = null;

/**
 * Lazily import SheetJS exactly once and cache the promise.
 * @returns {Promise<object>} SheetJS namespace
 */
function loadXlsx() {
  if (!_xlsxPromise) {
    _xlsxPromise = import(/* webpackIgnore: true */ XLSX_CDN).catch(err => {
      _xlsxPromise = null; // allow retry on next click
      throw err;
    });
  }
  return _xlsxPromise;
}

/**
 * Build a flat array of row objects for the "info" tab.
 * @param {object} moduleData
 * @param {string} instanceId
 * @returns {object[]}
 */
function buildInfoRows(moduleData, instanceId) {
  const info = moduleData.info ?? {};
  const rows = [];
  for (const [key, value] of Object.entries(info)) {
    rows.push({ Key: key, Value: value == null ? '' : String(value) });
  }
  if (rows.length === 0 && instanceId) {
    rows.push({ Key: 'instance_id', Value: instanceId });
  }
  return rows;
}

/**
 * Build row objects for the "functions" tab.
 * @param {object} moduleData
 * @returns {object[]}
 */
function buildFunctionsRows(moduleData) {
  const fns = moduleData.functions ?? [];
  return fns.map(fn => ({
    'Function Name': fn.name ?? fn.function_name ?? '',
    Type:            fn.type ?? '',
    Description:     fn.description ?? '',
    Arguments:       JSON.stringify(fn.args ?? fn.arguments ?? []),
  }));
}

/**
 * Build row objects for the "params" tab.
 * @param {object} moduleData
 * @returns {object[]}
 */
function buildParamsRows(moduleData) {
  const params = moduleData.params ?? {};
  return Object.entries(params).map(([key, p]) => ({
    Key:           key,
    'Display Name':p?.display_name ?? p?.displayname ?? '',
    Value:         p?.value == null ? '' : String(p.value),
    'Default':     p?.default_value == null ? '' : String(p.default_value),
    Type:          p?.type ?? '',
    Description:   p?.description ?? '',
  }));
}

/**
 * Build row objects for the "volatile" tab.
 * @param {object} moduleData
 * @returns {object[]}
 */
function buildVolatileRows(moduleData) {
  const vols = moduleData.volatiles ?? {};
  return Object.entries(vols).map(([key, v]) => ({
    Key:   key,
    Value: v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v),
  }));
}

/**
 * Build sheets array [{name, rows}] for the "feeds" tab.
 * @param {object} moduleData
 * @returns {Array<{name: string, rows: object[]}>}
 */
function buildFeedsSheets(moduleData) {
  const sheets = [];

  const mapFeedRows = feedArray => (feedArray ?? []).map(f => ({
    Timestamp:   f.ts ?? f.timestamp ?? '',
    State:       f.state ?? '',
    Data:        f.data == null ? '' : typeof f.data === 'object'
                   ? JSON.stringify(f.data)
                   : String(f.data),
    Description: f.description ?? '',
  }));

  sheets.push({ name: 'State Feeds',  rows: mapFeedRows(moduleData.stateFeeds)  });
  sheets.push({ name: 'Error Feeds',  rows: mapFeedRows(moduleData.errorFeeds)  });
  sheets.push({ name: 'News Feeds',   rows: mapFeedRows(moduleData.newsFeeds)   });
  return sheets;
}

/**
 * Build row objects for the "logs" tab.
 * @param {object} moduleData
 * @returns {object[]}
 */
function buildLogsRows(moduleData) {
  const lines = moduleData.logLines ?? [];
  return lines.map(l => ({
    Timestamp: l.ts ?? '',
    Level:     l.level ?? '',
    Logger:    l.logger ?? '',
    Message:   l.message ?? '',
  }));
}

/**
 * Trigger browser download of a Blob as a file.
 * @param {Uint8Array|ArrayBuffer} data
 * @param {string} filename
 */
function triggerDownload(data, filename) {
  const blob = new Blob([data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

/**
 * Build workbook and trigger xlsx download for the given tab / data.
 *
 * @param {object} XLSX - SheetJS namespace
 * @param {string} tab
 * @param {string} instanceId
 * @param {object} moduleData
 */
function generateXlsx(XLSX, tab, instanceId, moduleData) {
  const wb = XLSX.utils.book_new();
  const safeName = (instanceId ?? 'module').replace(/[^a-z0-9_-]/gi, '_').slice(0, 20);
  const filename = `${safeName}_${tab}_${new Date().toISOString().slice(0, 10)}.xlsx`;

  if (tab === 'feeds') {
    const sheets = buildFeedsSheets(moduleData);
    for (const { name, rows } of sheets) {
      const ws = rows.length > 0
        ? XLSX.utils.json_to_sheet(rows)
        : XLSX.utils.aoa_to_sheet([['No data']]);
      XLSX.utils.book_append_sheet(wb, ws, name);
    }
  } else {
    let rows;
    switch (tab) {
      case 'info':      rows = buildInfoRows(moduleData, instanceId); break;
      case 'functions': rows = buildFunctionsRows(moduleData);        break;
      case 'params':    rows = buildParamsRows(moduleData);           break;
      case 'volatile':  rows = buildVolatileRows(moduleData);         break;
      case 'logs':      rows = buildLogsRows(moduleData);             break;
      default:          rows = [];
    }
    const ws = rows.length > 0
      ? XLSX.utils.json_to_sheet(rows)
      : XLSX.utils.aoa_to_sheet([['No data']]);
    const sheetName = tab.charAt(0).toUpperCase() + tab.slice(1);
    XLSX.utils.book_append_sheet(wb, ws, sheetName);
  }

  const wbOut = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
  triggerDownload(wbOut, filename);
}

export default defineComponent({
  name: 'ModuleDetailExport',

  props: {
    /** Current detail tab: 'info' | 'functions' | 'params' | 'volatile' | 'feeds' | 'logs' */
    tab: {
      type: String,
      default: 'info',
    },
    /** Module instance ID — used in the downloaded filename */
    instanceId: {
      type: String,
      default: '',
    },
    /** Tab-specific data snapshot provided by the host */
    moduleData: {
      type: Object,
      default: () => ({}),
    },
  },

  setup(props) {
    const loading = ref(false);
    const error   = ref(null);

    const tabLabel = computed(() => {
      const labels = {
        info:      'Info',
        functions: 'Functions',
        params:    'Parameters',
        volatile:  'Volatile',
        feeds:     'Feeds',
        logs:      'Logs',
      };
      return labels[props.tab] ?? props.tab;
    });

    async function download() {
      if (loading.value) return;
      loading.value = true;
      error.value   = null;
      try {
        const XLSX = await loadXlsx();
        generateXlsx(XLSX, props.tab, props.instanceId, props.moduleData);
      } catch (e) {
        console.error('[module-detail-export] download error:', e);
        error.value = 'Export failed';
      } finally {
        loading.value = false;
      }
    }

    return { loading, error, tabLabel, download };
  },

  template: `
    <span class="vyra-detail-export">
      <button
        class="vyra-detail-export__btn"
        :disabled="loading"
        :title="'Download ' + tabLabel + ' as xlsx'"
        @click="download"
      >
        <span v-if="loading" class="vyra-detail-export__spinner">⏳</span>
        <span v-else class="vyra-detail-export__icon">⬇</span>
      </button>
      <span v-if="error" class="vyra-detail-export__error" :title="error">⚠</span>

      <style>
        .vyra-detail-export {
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }
        .vyra-detail-export__btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 28px;
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
      </style>
    </span>
  `,
});
