/**
 * Module Count Widget — VYRA Plugin
 * Scope:  backend → v2_modulemanager (MODULE)
 *         frontend → v2_dashboard / home-widget slot
 *
 * Polls GET /v2_modulemanager/api/modules/instances every `refreshIntervalMs`
 * milliseconds and displays the live count of installed modules (and
 * optionally the total instance count) as a dashboard home-widget.
 *
 * API shape (ModulesResponse):
 *   {
 *     modules:          { [name]: ModuleInstance[] }
 *     total_modules:    number    // number of distinct module types
 *     total_instances:  number    // sum of all instances
 *   }
 */

const { defineComponent, ref, onMounted, onUnmounted, computed } = window.Vue;

const MODULES_API = '/v2_modulemanager/api/modules/instances';

export default defineComponent({
  name: 'ModuleCountWidget',

  props: {
    /** Display title shown in the widget header (from config_overlay). */
    label: {
      type: String,
      default: 'Installed Modules',
    },
    /** Polling interval in ms (from config_overlay). */
    refreshIntervalMs: {
      type: Number,
      default: 5000,
    },
    /** Whether to show total_instances below the module count. */
    showInstances: {
      type: Boolean,
      default: true,
    },
  },

  setup(props) {
    const totalModules   = ref(null);   // null = not yet loaded
    const totalInstances = ref(null);
    const moduleNames    = ref([]);     // list of module name strings
    const loading        = ref(false);
    const error          = ref(null);
    const lastUpdated    = ref(null);

    let pollTimer = null;

    /** Format HH:MM:SS timestamp for the "last updated" indicator. */
    const formattedTime = computed(() => {
      if (!lastUpdated.value) return null;
      return lastUpdated.value.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    });

    /**
     * Fetch the module instance list from the modulemanager REST API and
     * update local reactive state.
     */
    const fetchModules = async () => {
      if (loading.value) return;
      loading.value = true;
      error.value = null;
      try {
        const res = await fetch(MODULES_API, { credentials: 'same-origin' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        /** @type {{ total_modules: number, total_instances: number, modules: Record<string, unknown[]> }} */
        const data = await res.json();
        totalModules.value   = data.total_modules   ?? Object.keys(data.modules ?? {}).length;
        totalInstances.value = data.total_instances ?? 0;
        moduleNames.value    = Object.keys(data.modules ?? {});
        lastUpdated.value    = new Date();
      } catch (e) {
        error.value = `API unavailable (${e.message})`;
      } finally {
        loading.value = false;
      }
    };

    /** Start polling on component mount. */
    onMounted(() => {
      fetchModules();
      pollTimer = setInterval(fetchModules, props.refreshIntervalMs);
    });

    /** Clean up the interval on component teardown. */
    onUnmounted(() => {
      if (pollTimer !== null) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    });

    return {
      totalModules,
      totalInstances,
      moduleNames,
      loading,
      error,
      formattedTime,
      fetchModules,
    };
  },

  template: `
    <div class="vyra-module-count-widget">

      <!-- Header row ─────────────────────────────────────────────── -->
      <div class="vyra-module-count-widget__header">
        <span class="vyra-module-count-widget__title">{{ label }}</span>
        <span
          class="vyra-module-count-widget__badge"
          :class="error ? 'vyra-module-count-widget__badge--offline'
                        : 'vyra-module-count-widget__badge--live'"
        >{{ error ? 'OFFLINE' : 'LIVE' }}</span>
      </div>

      <!-- Primary value ──────────────────────────────────────────── -->
      <div
        class="vyra-module-count-widget__value"
        :class="{ 'vyra-module-count-widget__value--loading': loading && totalModules === null }"
        title="Total distinct module types installed"
      >{{ totalModules !== null ? totalModules : '–' }}</div>
      <div class="vyra-module-count-widget__unit">modules</div>

      <!-- Secondary: instance count ──────────────────────────────── -->
      <div v-if="showInstances && !error" class="vyra-module-count-widget__secondary">
        <span class="vyra-module-count-widget__secondary-label">instances</span>
        <span class="vyra-module-count-widget__secondary-value">
          {{ totalInstances !== null ? totalInstances : '–' }}
        </span>
      </div>

      <!-- Module name list ───────────────────────────────────────── -->
      <ul v-if="moduleNames.length > 0 && !error" class="vyra-module-count-widget__list">
        <li
          v-for="name in moduleNames"
          :key="name"
          class="vyra-module-count-widget__list-item"
        >{{ name }}</li>
      </ul>

      <!-- Error state ────────────────────────────────────────────── -->
      <div v-if="error" class="vyra-module-count-widget__error">{{ error }}</div>

      <!-- Footer: last-updated + manual refresh ──────────────────── -->
      <div class="vyra-module-count-widget__footer">
        <span v-if="formattedTime" class="vyra-module-count-widget__ts">
          updated {{ formattedTime }}
        </span>
        <button
          class="vyra-module-count-widget__refresh-btn"
          :disabled="loading"
          @click="fetchModules"
          title="Refresh now"
        >↻</button>
      </div>

    </div>
  `,
});
