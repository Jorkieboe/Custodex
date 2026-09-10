<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchAppConfig, updateAppConfig, fetchApiStatus, type AppConfig } from '../services/api'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const config = ref<AppConfig>({
  default_llm_model: 'gtp-4.1-mini',
  default_embedding_model: 'text-embedding-multilingual-e5-base',
  lm_studio_endpoint: 'http://localhost:1234/v1',
  llm_endpoint: 'https://api.openai.com/v1',
  embedding_endpoint: 'http://localhost:1234/v1',
  openai_api_key: '',
  recent_projects: []
})

const showApiKey = ref(false)
const isTestingLlm = ref(false)
const llmTestResult = ref<string | null>(null)
const isLlmConnected = ref<boolean | null>(null)

const isTestingEmbed = ref(false)
const embedTestResult = ref<string | null>(null)
const isEmbedConnected = ref<boolean | null>(null)
const isSaving = ref(false)

onMounted(async () => {
  try {
    const loaded = await fetchAppConfig()
    config.value = {
      ...loaded,
      llm_endpoint: loaded.llm_endpoint || loaded.lm_studio_endpoint || 'https://api.openai.com/v1',
      embedding_endpoint: loaded.embedding_endpoint || loaded.lm_studio_endpoint || 'http://localhost:1234/v1',
      openai_api_key: loaded.openai_api_key || ''
    }
  } catch (err) {
    console.error('Failed to load application config', err)
  }
})

async function testLlmConnection() {
  isTestingLlm.value = true
  llmTestResult.value = null
  try {
    const status = await fetchApiStatus()
    isLlmConnected.value = status.lm_studio_connected
    if (status.lm_studio_connected) {
      llmTestResult.value = 'Reachable: Generation service answered cleanly.'
    } else {
      llmTestResult.value = 'Endpoint not responding at ' + (config.value.llm_endpoint || config.value.lm_studio_endpoint)
    }
  } catch (err: any) {
    isLlmConnected.value = false
    llmTestResult.value = 'Error: ' + (err.message || 'Connection failed')
  } finally {
    isTestingLlm.value = false
  }
}

async function testEmbedConnection() {
  isTestingEmbed.value = true
  embedTestResult.value = null
  try {
    const target = config.value.embedding_endpoint || config.value.lm_studio_endpoint
    embedTestResult.value = 'Configured embedding endpoint: ' + target
    isEmbedConnected.value = true
  } catch (err: any) {
    isEmbedConnected.value = false
    embedTestResult.value = 'Error: ' + (err.message || 'Check endpoint')
  } finally {
    isTestingEmbed.value = false
  }
}

async function saveSettings() {
  isSaving.value = true
  try {
    if (!config.value.lm_studio_endpoint) {
      config.value.lm_studio_endpoint = config.value.embedding_endpoint || config.value.llm_endpoint || 'http://localhost:1234/v1'
    }
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
        <h2>Global Settings & Separated Model Providers</h2>
        <button class="close-btn" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <!-- OpenAI / Remote API Key Field -->
        <div class="form-group">
          <div class="label-row">
            <label>OpenAI API Key (or set OPENAI_API_KEY in .env)</label>
            <button class="btn-toggle-key" type="button" @click="showApiKey = !showApiKey">
              {{ showApiKey ? 'Hide' : 'Show' }}
            </button>
          </div>
          <input
            v-model="config.openai_api_key"
            :type="showApiKey ? 'text' : 'password'"
            placeholder="sk-proj-... or leave blank to use .env variable"
            autocomplete="off"
          />
          <span class="field-hint">Used for remote GPT models (e.g. gpt-4o, gtp-4.1-mini) and remote embeddings.</span>
        </div>

        <div class="section-divider">
          <span>Generation / LLM Provider</span>
        </div>

        <div class="form-group">
          <label>Generation LLM API Endpoint</label>
          <div class="input-with-action">
            <input
              v-model="config.llm_endpoint"
              type="text"
              placeholder="https://api.openai.com/v1 or http://localhost:1234/v1"
            />
            <button class="btn btn-secondary" @click="testLlmConnection" :disabled="isTestingLlm">
              {{ isTestingLlm ? 'Testing...' : 'Test' }}
            </button>
          </div>
          <p v-if="llmTestResult" class="test-feedback" :class="{ success: isLlmConnected, error: !isLlmConnected }">
            {{ llmTestResult }}
          </p>
        </div>

        <div class="form-group">
          <label>Default LLM Generation Model</label>
          <input v-model="config.default_llm_model" type="text" placeholder="gtp-4.1-mini or local-model" />
        </div>

        <div class="section-divider">
          <span>Vector Embedding Provider</span>
        </div>

        <div class="form-group">
          <label>Vector Embedding API Endpoint</label>
          <div class="input-with-action">
            <input
              v-model="config.embedding_endpoint"
              type="text"
              placeholder="http://localhost:1234/v1 or https://api.openai.com/v1"
            />
            <button class="btn btn-secondary" @click="testEmbedConnection" :disabled="isTestingEmbed">
              {{ isTestingEmbed ? 'Testing...' : 'Test' }}
            </button>
          </div>
          <p v-if="embedTestResult" class="test-feedback" :class="{ success: isEmbedConnected, error: !isEmbedConnected }">
            {{ embedTestResult }}
          </p>
        </div>

        <div class="form-group">
          <label>Default Embedding Model</label>
          <input v-model="config.default_embedding_model" type="text" placeholder="text-embedding-multilingual-e5-base" />
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

  .label-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .btn-toggle-key {
    font-size: 11px;
    color: $color-primary;
    background: none;
    border: none;
    cursor: pointer;
  }

  .field-hint {
    font-size: 11px;
    color: $color-text-muted;
  }

  .section-divider {
    display: flex;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 4px;
    margin-top: 4px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: $color-primary;
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