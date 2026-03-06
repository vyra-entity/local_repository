/**
 * Counter Widget — VYRA Plugin
 * Scope: v2_dashboard / Slot: home-widget
 *
 * Lädt den aktuellen Zählerstand vom v2_modulemanager und
 * inkrementiert ihn bei Klick. Die Logik (Zähler-State) lebt
 * im PluginRuntime des v2_modulemanager backends.
 *
 * Abhängig von Phase 4 API:
 *   GET  /v2_modulemanager/api/plugin/counter-widget/state
 *   POST /v2_modulemanager/api/plugin/counter-widget/increment
 */

const { defineComponent, ref, onMounted, computed } = window.Vue;

const API_BASE = '/v2_modulemanager/api/plugin/counter-widget';

export default defineComponent({
  name: 'CounterWidget',

  props: {
    // config_overlay Felder aus PluginAssignment
    label: {
      type: String,
      default: 'Counter'
    },
    step: {
      type: Number,
      default: 1
    }
  },

  setup(props) {
    const count    = ref(null);   // null = noch nicht geladen
    const loading  = ref(false);
    const error    = ref(null);
    const apiReady = ref(false);

    const displayCount = computed(() =>
      count.value === null ? '–' : count.value
    );

    const fetchState = async () => {
      try {
        const res = await fetch(`${API_BASE}/state`, { credentials: 'same-origin' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        count.value = data.count;
        apiReady.value = true;
        error.value = null;
      } catch (e) {
        error.value = 'API nicht verfügbar';
        apiReady.value = false;
      }
    };

    const increment = async () => {
      if (loading.value) return;
      loading.value = true;
      error.value = null;
      try {
        const res = await fetch(`${API_BASE}/increment`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ step: props.step })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        count.value = data.count;
      } catch (e) {
        error.value = 'Fehler beim Inkrementieren';
      } finally {
        loading.value = false;
      }
    };

    const reset = async () => {
      if (loading.value) return;
      loading.value = true;
      try {
        const res = await fetch(`${API_BASE}/reset`, {
          method: 'POST',
          credentials: 'same-origin'
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        count.value = data.count;
      } catch (e) {
        error.value = 'Fehler beim Reset';
      } finally {
        loading.value = false;
      }
    };

    onMounted(fetchState);

    return { count, displayCount, loading, error, apiReady, increment, reset };
  },

  template: `
    <div class="vyra-counter-widget">
      <div class="vyra-counter-widget__header">
        <span class="vyra-counter-widget__title">{{ label }}</span>
        <span v-if="!apiReady" class="vyra-counter-widget__badge vyra-counter-widget__badge--offline">offline</span>
      </div>

      <div class="vyra-counter-widget__value">{{ displayCount }}</div>

      <div class="vyra-counter-widget__actions">
        <button
          class="vyra-counter-widget__btn vyra-counter-widget__btn--increment"
          :disabled="loading || !apiReady"
          @click="increment"
        >
          <span v-if="loading">…</span>
          <span v-else>+{{ step }}</span>
        </button>

        <button
          class="vyra-counter-widget__btn vyra-counter-widget__btn--reset"
          :disabled="loading || !apiReady"
          @click="reset"
          title="Zurücksetzen"
        >↺</button>
      </div>

      <div v-if="error" class="vyra-counter-widget__error">{{ error }}</div>
    </div>
  `
});
