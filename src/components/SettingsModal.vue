<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchAppConfig, updateAppConfig, fetchApiStatus, type AppConfig } from '../services/api'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const config = ref<AppConfig>({
  default_llm_model: 'local-model',
  default_embedding_model: 'text-embedding-nomic-embed-text-v1.5',
  lm_studio_endpoint: 'http://localhost:1234/v1',
  recent_projects: []
})

const isTesting = ref(false)
const testResult = ref<string | null>(null)
const isConnected = ref<boolean | null>(null)
const isSaving = ref(false)

onMounted(async () => {
  try {
    const loaded = await fetchAppConfig()
    config.value = loaded
  } catch (err) {
    console.error('Failed to load application config', err)
  }
})

async function testConnection() {
  isTesting.value = true
  testResult.value = null
  try {
    const status = await fetchApiStatus()
    isConnected.value = status.lm_studio_connected
    if (status.lm_studio_connected) {
      testResult.value = 'Connection successful: LM Studio is reachable.'
    } else {
      testResult.value = 'Unreachable: LM Studio is not responding at ' + config.value.lm_studio_endpoint
    }
  } catch (err: any) {
    isConnected.value = false
    testResult.value = 'Error testing connection: ' + (err.message || 'Network error')
  } finally {
    isTesting.value = false
  }
}

async function saveSettings() {
  isSaving.value = true
  try {
    await updateAppConfig(config.value)
    emit('close')
  } catch (err) {
    console.error('Failed to update config', err)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal-card">
      <div class="modal-header">
        <h2>Global Settings & Model Connectivity</h2>
        <button class="close-btn" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <div class="form-group">
          <label>LM Studio API Endpoint</label>
          <div class="input-with-action">
            <input v-model="config.lm_studio_endpoint" type="text" placeholder="http://localhost:1234/v1" />
            <button class="btn btn-secondary" @click="testConnection" :disabled="isTesting">
              {{ isTesting ? 'Testing...' : 'Test' }}
            </button>
          </div>
          <p v-if="testResult" class="test-feedback" :class="{ success: isConnected, error: !isConnected }">
            {{ testResult }}
          </p>
        </div>

        <div class="form-group">
          <label>Default LLM Model Identifier</label>
          <input v-model="config.default_llm_model" type="text" placeholder="local-model" />
        </div>

        <div class="form-group">
          <label>Default Embedding Model Identifier</label>
          <input v-model="config.default_embedding_model" type="text" placeholder="text-embedding-nomic-embed-text-v1.5" />
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn btn-secondary" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" @click="saveSettings" :disabled="isSaving">
          {{ isSaving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../styles/variables' as *;

.modal-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  width: 520px;
  max-width: 90vw;
  box-shadow: $shadow-modal;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid $color-border;
  display: flex;
  justify-content: space-between;
  align-items: center;

  h2 {
    font-size: 16px;
    font-weight: 600;
  }

  .close-btn {
    color: $color-text-secondary;
    font-size: 16px;
    &:hover {
      color: $color-text-primary;
    }
  }
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 12px;
    font-weight: 600;
    color: $color-text-secondary;
    text-transform: uppercase;
  }

  input {
    background-color: rgba(0, 0, 0, 0.3);
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 8px 12px;
    color: $color-text-primary;
    outline: none;

    &:focus {
      border-color: $color-primary;
    }
  }
}

.input-with-action {
  display: flex;
  gap: 8px;

  input {
    flex: 1;
  }
}

.test-feedback {
  font-size: 12px;
  margin-top: 4px;

  &.success {
    color: $color-status-current;
  }

  &.error {
    color: $color-status-missing;
  }
}

.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid $color-border;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  padding: 6px 14px;
  border-radius: $radius-md;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;

  &.btn-primary {
    background-color: $color-primary;
    color: #000;
    &:hover:not(:disabled) {
      background-color: $color-primary-hover;
    }
  }

  &.btn-secondary {
    background-color: $color-surface-hover;
    color: $color-text-primary;
    border: 1px solid $color-border;
    &:hover:not(:disabled) {
      background-color: lighten(#334155, 5%);
    }
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>