<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'

const store = useWorkspaceStore()
let eventSource: EventSource | null = null

const forceOverwrite = ref(false)

const progressPercentage = computed(() => {
  const status = store.metadataJobStatus
  if (!status.total_partitions || status.total_partitions === 0) return 0
  return Math.min(100, Math.round((status.completed_partitions / status.total_partitions) * 100))
})

function connectSSE() {
  if (!store.currentProject) return
  if (eventSource) eventSource.close()

  const url = `http://localhost:8000/api/projects/${store.currentProject.id}/jobs/metadata/stream`
  eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      const ev = payload.event
      const data = payload.data

      if (ev === 'state') {
        store.metadataJobStatus = data
      } else if (ev === 'partition_start') {
        store.metadataJobStatus.completed_partitions = data.partition_index - 1
        store.metadataJobStatus.total_partitions = data.total_partitions
      } else if (ev === 'chunk_progress') {
        store.metadataJobStatus.completed_chunks = data.completed_chunks
        store.metadataJobStatus.total_chunks = data.total_chunks
      } else if (ev === 'partition_complete') {
        store.metadataJobStatus.completed_partitions = data.partition_index
        store.metadataJobStatus.total_partitions = data.total_partitions
      } else if (ev === 'completed') {
        store.metadataJobStatus.status = 'completed'
        if (eventSource) eventSource.close()
      } else if (ev === 'error') {
        store.metadataJobStatus.status = 'failed'
        store.metadataJobStatus.last_error = data.error
        if (eventSource) eventSource.close()
      }
    } catch (e) {
      console.error('SSE JSON parse error:', e)
    }
  }

  eventSource.onerror = () => {
    if (store.metadataJobStatus.status === 'running') {
      store.metadataJobStatus.status = 'failed'
      store.metadataJobStatus.last_error = 'Connection to server interrupted'
    }
    if (eventSource) eventSource.close()
  }
}

async function handleStart() {
  await store.triggerMetadataExtraction({ force_overwrite: forceOverwrite.value, resume: false })
  connectSSE()
}

async function handleResume() {
  await store.triggerMetadataExtraction({ force_overwrite: forceOverwrite.value, resume: true })
  connectSSE()
}

onMounted(() => {
  if (store.metadataJobStatus.status === 'running') {
    connectSSE()
  }
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
})
</script>

<template>
  <div v-if="store.isBatchModalOpen" class="modal-backdrop">
    <div class="modal-card">
      <div class="modal-header">
        <h3>Partitioned Metadata Extraction</h3>
        <button class="btn-close" @click="store.closeBatchModal">✕</button>
      </div>

      <div class="modal-body">
        <p class="modal-desc">
          Extract structured metadata chunk-by-chunk using LM Studio. Batches are checkpointed in SQLite so interruptions can be resumed cleanly.
        </p>

        <!-- Progress View when running or failed -->
        <div v-if="store.metadataJobStatus.status !== 'idle'" class="progress-section">
          <div class="progress-labels">
            <span class="progress-title">
              Part {{ store.metadataJobStatus.completed_partitions }} of {{ store.metadataJobStatus.total_partitions || '?' }}
            </span>
            <span class="progress-chunks">
              Chunk {{ store.metadataJobStatus.completed_chunks }} / {{ store.metadataJobStatus.total_chunks }}
            </span>
          </div>

          <div class="progress-bar-bg">
            <div
              class="progress-bar-fill"
              :class="{
                'fill-running': store.metadataJobStatus.status === 'running',
                'fill-completed': store.metadataJobStatus.status === 'completed',
                'fill-failed': store.metadataJobStatus.status === 'failed'
              }"
              :style="{ width: `${progressPercentage}%` }"
            ></div>
          </div>

          <div class="status-indicator">
            <span v-if="store.metadataJobStatus.status === 'running'" class="status-running">
              ⏳ Processing partition batch...
            </span>
            <span v-else-if="store.metadataJobStatus.status === 'completed'" class="status-completed">
              ✅ All partitions completed successfully!
            </span>
            <span v-else-if="store.metadataJobStatus.status === 'failed'" class="status-failed">
              ❌ Extraction stopped due to an error
            </span>
          </div>

          <!-- Error Alert Card -->
          <div v-if="store.metadataJobStatus.status === 'failed'" class="error-diagnostic-card">
            <span class="error-title">Diagnostic Diagnostic:</span>
            <p class="error-msg">{{ store.metadataJobStatus.last_error }}</p>
            <span class="error-hint">Previously completed partitions remain safely committed in the database.</span>
          </div>
        </div>

        <!-- Options -->
        <div class="options-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="forceOverwrite" />
            <span>Force Overwrite (replaces fields edited by humans)</span>
          </label>
        </div>
      </div>

      <div class="modal-footer">
        <button
          v-if="store.metadataJobStatus.status === 'failed'"
          class="btn btn-primary"
          @click="handleResume"
        >
          Resume Extraction
        </button>

        <button
          v-else-if="store.metadataJobStatus.status === 'running'"
          class="btn btn-secondary"
          @click="store.closeBatchModal"
        >
          Run in Background
        </button>

        <button
          v-else
          class="btn btn-primary"
          @click="handleStart"
        >
          Start Extraction
        </button>

        <button class="btn btn-secondary" @click="store.closeBatchModal">
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.modal-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  width: 500px;
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid $color-border;
  display: flex;
  justify-content: space-between;
  align-items: center;

  h3 {
    font-size: 16px;
    font-weight: 700;
  }

  .btn-close {
    background: transparent;
    color: $color-text-muted;
    font-size: 16px;
    &:hover { color: $color-text-primary; }
  }
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-desc {
  font-size: 13px;
  color: $color-text-secondary;
  line-height: 1.4;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid $color-border;
  border-radius: $radius-md;
  padding: 14px;
}

.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
}

.progress-bar-bg {
  height: 8px;
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  transition: width 0.3s ease;

  &.fill-running {
    background-color: $color-primary;
  }

  &.fill-completed {
    background-color: $color-status-current;
  }

  &.fill-failed {
    background-color: $color-status-missing;
  }
}

.status-indicator {
  font-size: 12px;

  .status-running { color: $color-primary; }
  .status-completed { color: $color-status-current; }
  .status-failed { color: $color-status-missing; }
}

.error-diagnostic-card {
  background-color: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: $radius-sm;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;

  .error-title {
    font-size: 11px;
    font-weight: 700;
    color: $color-status-missing;
    text-transform: uppercase;
  }

  .error-msg {
    font-size: 12px;
    color: $color-text-primary;
    font-family: $font-family-mono;
  }

  .error-hint {
    font-size: 11px;
    color: $color-text-muted;
  }
}

.options-group {
  display: flex;
  flex-direction: column;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: $color-text-secondary;
  cursor: pointer;
}

.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid $color-border;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn {
  padding: 7px 16px;
  border-radius: $radius-md;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;

  &.btn-primary {
    background-color: $color-primary;
    color: #000;
    font-weight: 600;
  }

  &.btn-secondary {
    background-color: $color-surface-hover;
    color: $color-text-primary;
    border: 1px solid $color-border;
  }
}
</style>