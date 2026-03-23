<template>
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const API_BASE = '/v2_modulemanager/api/plugin/counter-widget'

const props = withDefaults(defineProps<{
  label?: string
  step?: number
}>(), {
  label: 'Counter',
  step: 1,
})

const count    = ref<number | null>(null)
const loading  = ref(false)
const error    = ref<string | null>(null)
const apiReady = ref(false)

const displayCount = computed(() => count.value === null ? '–' : count.value)

const fetchState = async () => {
  try {
    const res = await fetch(`${API_BASE}/state`, { credentials: 'same-origin' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    count.value = data.count
    apiReady.value = true
    error.value = null
  } catch {
    error.value = 'API nicht verfügbar'
    apiReady.value = false
  }
}

const increment = async () => {
  if (loading.value) return
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`${API_BASE}/increment`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: props.step }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    count.value = data.count
  } catch {
    error.value = 'Fehler beim Inkrementieren'
  } finally {
    loading.value = false
  }
}

const reset = async () => {
  if (loading.value) return
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/reset`, {
      method: 'POST',
      credentials: 'same-origin',
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    count.value = data.count
  } catch {
    error.value = 'Fehler beim Reset'
  } finally {
    loading.value = false
  }
}

onMounted(fetchState)
</script>
