<template>
  <div class="vyra-module-count-widget">

    <!-- Header row -->
    <div class="vyra-module-count-widget__header">
      <span class="vyra-module-count-widget__title">{{ label }}</span>
      <span
        class="vyra-module-count-widget__badge"
        :class="error ? 'vyra-module-count-widget__badge--offline' : 'vyra-module-count-widget__badge--live'"
      >{{ error ? 'OFFLINE' : 'LIVE' }}</span>
    </div>

    <!-- Primary value -->
    <div
      class="vyra-module-count-widget__value"
      :class="{ 'vyra-module-count-widget__value--loading': loading && totalModules === null }"
      title="Total distinct module types installed"
    >{{ totalModules !== null ? totalModules : '–' }}</div>
    <div class="vyra-module-count-widget__unit">modules</div>

    <!-- Secondary: instance count -->
    <div v-if="showInstances && !error" class="vyra-module-count-widget__secondary">
      <span class="vyra-module-count-widget__secondary-label">instances</span>
      <span class="vyra-module-count-widget__secondary-value">
        {{ totalInstances !== null ? totalInstances : '–' }}
      </span>
    </div>

    <!-- Module name list -->
    <ul v-if="moduleNames.length > 0 && !error" class="vyra-module-count-widget__list">
      <li v-for="name in moduleNames" :key="name" class="vyra-module-count-widget__list-item">{{ name }}</li>
    </ul>

    <!-- Error state -->
    <div v-if="error" class="vyra-module-count-widget__error">{{ error }}</div>

    <!-- Footer: last-updated + manual refresh -->
    <div class="vyra-module-count-widget__footer">
      <span v-if="formattedTime" class="vyra-module-count-widget__ts">updated {{ formattedTime }}</span>
      <button
        class="vyra-module-count-widget__refresh-btn"
        :disabled="loading"
        @click="fetchModules"
        title="Refresh now"
      >↻</button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const MODULES_API = '/v2_modulemanager/api/modules/instances'

const props = withDefaults(defineProps<{
  label?: string
  refreshIntervalMs?: number
  showInstances?: boolean
}>(), {
  label: 'Installed Modules',
  refreshIntervalMs: 5000,
  showInstances: true,
})

const totalModules   = ref<number | null>(null)
const totalInstances = ref<number | null>(null)
const moduleNames    = ref<string[]>([])
const loading        = ref(false)
const error          = ref<string | null>(null)
const lastUpdated    = ref<Date | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

const formattedTime = computed(() => {
  if (!lastUpdated.value) return null
  return lastUpdated.value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
})

const fetchModules = async () => {
  if (loading.value) return
  loading.value = true
  error.value = null
  try {
    const res = await fetch(MODULES_API, { credentials: 'same-origin' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    totalModules.value   = data.total_modules   ?? Object.keys(data.modules ?? {}).length
    totalInstances.value = data.total_instances ?? 0
    moduleNames.value    = Object.keys(data.modules ?? {})
    lastUpdated.value    = new Date()
  } catch (e: any) {
    error.value = `API unavailable (${e.message})`
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchModules()
  pollTimer = setInterval(fetchModules, props.refreshIntervalMs)
})

onUnmounted(() => {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>
