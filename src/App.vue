<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchApiStatus, type ApiStatus } from './services/api'

const loading = ref(true)
const error = ref<string | null>(null)
const statusData = ref<ApiStatus | null>(null)

async function checkStatus() {
  loading.value = true
  error.value = null
  try {
    statusData.value = await fetchApiStatus()
  } catch (err: any) {
    error.value = err.message || 'Failed to connect to Custodex backend service'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  checkStatus()
})
</script>

<template>
  <div class="workbench-container">
    <header class="workbench-header">
      <div class="brand">
        <span class="brand-icon">📦</span>
        <h1 class="brand-title">Custodex</h1>
        <span class="brand-tag">Workbench</span>
      </div>
      <button class="refresh-btn" @click="checkStatus" :disabled="loading">
        {{ loading ? 'Checking...' : 'Refresh Status' }}
      </button>
    </header>

    <main class="workbench-content">
      <div class="card status-card">
        <h2 class="card-title">System Liveness & Connectivity</h2>

        <div v-if="loading" class="status-loading">
          Connecting to Custodex backend...
        </div>

        <div v-else-if="error" class="status-alert error">
          <span class="indicator indicator-missing"></span>
          <div>
            <strong>Backend Connection Offline:</strong>
            <p>{{ error }}</p>
          </div>
        </div>

        <div v-else-if="statusData" class="status-details">
          <div class="status-row">
            <span class="label">Backend API:</span>
            <span class="badge badge-current">
              <span class="indicator indicator-current"></span>
              {{ statusData.status.toUpperCase() }}
            </span>
          </div>

          <div class="status-row">
            <span class="label">LM Studio Provider:</span>
            <span
              class="badge"
              :class="statusData.lm_studio_connected ? 'badge-current' : 'badge-stale'"
            >
              <span
                class="indicator"
                :class="statusData.lm_studio_connected ? 'indicator-current' : 'indicator-stale'"
              ></span>
              {{ statusData.lm_studio_connected ? 'Connected' : 'Unreachable (Optional for local AI)' }}
            </span>
          </div>

          <div class="status-row">
            <span class="label">LM Studio Endpoint:</span>
            <code class="code-value">{{ statusData.lm_studio_endpoint }}</code>
          </div>

          <div class="status-row">
            <span class="label">Default LLM Model:</span>
            <code class="code-value">{{ statusData.default_llm_model }}</code>
          </div>

          <div class="status-row">
            <span class="label">Default Embedding Model:</span>
            <code class="code-value">{{ statusData.default_embedding_model }}</code>
          </div>
        </div>
      </div>

      <div class="card tokens-preview-card">
        <h2 class="card-title">Status Indicator Tokens</h2>
        <div class="tokens-list">
          <div class="token-item">
            <span class="badge badge-current">
              <span class="indicator indicator-current"></span>
              Current (Synchronized)
            </span>
          </div>
          <div class="token-item">
            <span class="badge badge-stale">
              <span class="indicator indicator-stale"></span>
              Stale (Pending Refresh)
            </span>
          </div>
          <div class="token-item">
            <span class="badge badge-missing">
              <span class="indicator indicator-missing"></span>
              Missing (Uncalculated)
            </span>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped lang="scss">
@use './styles/variables' as *;

.workbench-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: $color-bg;
}

.workbench-header {
  height: $header-height;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;

  .brand-icon {
    font-size: 20px;
  }

  .brand-title {
    font-size: 18px;
    font-weight: 700;
    color: $color-text-primary;
    letter-spacing: -0.02em;
  }

  .brand-tag {
    font-size: 11px;
    text-transform: uppercase;
    background-color: $color-surface-hover;
    color: $color-primary;
    padding: 2px 8px;
    border-radius: $radius-sm;
    font-weight: 600;
    letter-spacing: 0.05em;
  }
}

.refresh-btn {
  background-color: $color-surface-hover;
  color: $color-text-primary;
  border: 1px solid $color-border;
  padding: 6px 14px;
  border-radius: $radius-md;
  transition: all 0.15s ease;

  &:hover:not(:disabled) {
    background-color: lighten(#334155, 5%);
    border-color: $color-primary;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.workbench-content {
  flex: 1;
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  padding: 24px;

  .card-title {
    font-size: 16px;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 20px;
  }
}

.status-loading {
  color: $color-text-secondary;
}

.status-alert.error {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background-color: $color-status-missing-bg;
  border: 1px solid $color-status-missing;
  padding: 16px;
  border-radius: $radius-md;
  color: lighten(#ef4444, 25%);

  p {
    margin-top: 4px;
    font-size: 13px;
    color: $color-text-secondary;
  }
}

.status-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);

  &:last-child {
    border-bottom: none;
  }

  .label {
    color: $color-text-secondary;
    font-size: 13px;
  }
}

.code-value {
  font-family: $font-family-mono;
  background-color: rgba(0, 0, 0, 0.3);
  padding: 2px 8px;
  border-radius: $radius-sm;
  color: $color-primary;
  font-size: 13px;
}

.indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;

  &.indicator-current {
    background-color: $color-status-current;
  }

  &.indicator-stale {
    background-color: $color-status-stale;
  }

  &.indicator-missing {
    background-color: $color-status-missing;
  }
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: $radius-sm;
  font-size: 12px;
  font-weight: 500;

  &.badge-current {
    background-color: $color-status-current-bg;
    color: $color-status-current;
  }

  &.badge-stale {
    background-color: $color-status-stale-bg;
    color: $color-status-stale;
  }

  &.badge-missing {
    background-color: $color-status-missing-bg;
    color: $color-status-missing;
  }
}

.tokens-list {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
</style>