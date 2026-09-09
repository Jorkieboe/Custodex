<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const fileInput = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)

function triggerFileInput() {
  fileInput.value?.click()
}

async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  const files = Array.from(target.files)
  await store.uploadFiles(files)
  target.value = ''
}

async function handleDrop(event: DragEvent) {
  isDragging.value = false
  if (!event.dataTransfer?.files || event.dataTransfer.files.length === 0) return
  const files = Array.from(event.dataTransfer.files)
  await store.uploadFiles(files)
}
</script>

<template>
  <div class="ingestion-view">
    <div class="ingestion-header">
      <h2>Source Document Ingestion</h2>
      <p class="desc">Import DOCX, PDF, Markdown, or TXT documents. Hierarchies and nodes are preserved with persistent UUIDs.</p>
    </div>

    <div
      class="dropzone"
      :class="{ dragging: isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".docx,.pdf,.md,.markdown,.txt"
        style="display: none"
        @change="handleFileSelect"
      />
      <div class="dropzone-content">
        <span class="drop-icon">📄</span>
        <p class="drop-title">Click or drag documents here to import</p>
        <span class="drop-hint">Supported: .docx (heading tree), .pdf, .md, .txt</span>
      </div>
    </div>

    <div class="documents-section">
      <h3>Imported Documents ({{ store.documents.length }})</h3>

      <div v-if="store.documents.length === 0" class="empty-docs">
        No documents imported yet. Drag in a document to get started.
      </div>

      <div v-else class="doc-list">
        <div
          v-for="doc in store.documents"
          :key="doc.id"
          class="doc-card"
        >
          <div class="doc-main">
            <span class="format-badge">{{ doc.file_type.toUpperCase() }}</span>
            <div class="doc-meta">
              <h4>{{ doc.filename }}</h4>
              <span class="doc-counts">{{ doc.total_nodes }} structural nodes</span>
            </div>
          </div>

          <div class="doc-actions">
            <button
              class="btn btn-sm btn-action"
              @click.stop="store.setStep('chunks')"
            >
              Open in Canvas
            </button>
            <button
              class="btn btn-sm btn-danger"
              @click.stop="store.removeDocument(doc.id)"
              title="Delete document"
            >
              ✕
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../styles/variables' as *;

.ingestion-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.ingestion-header {
  h2 {
    font-size: 22px;
    font-weight: 700;
  }
  .desc {
    font-size: 14px;
    color: $color-text-secondary;
    margin-top: 4px;
  }
}

.dropzone {
  background-color: rgba(0, 0, 0, 0.2);
  border: 2px dashed $color-border;
  border-radius: $radius-lg;
  padding: 48px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover, &.dragging {
    border-color: $color-primary;
    background-color: rgba(56, 189, 248, 0.05);
  }

  .drop-icon {
    font-size: 32px;
  }
  .drop-title {
    font-size: 15px;
    font-weight: 600;
    margin-top: 10px;
  }
  .drop-hint {
    font-size: 12px;
    color: $color-text-muted;
    margin-top: 4px;
  }
}

.documents-section {
  display: flex;
  flex-direction: column;
  gap: 12px;

  h3 {
    font-size: 16px;
    font-weight: 600;
  }
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  cursor: pointer;
  transition: all 0.15s ease;
}

.doc-main {
  display: flex;
  align-items: center;
  gap: 12px;

  .format-badge {
    font-size: 10px;
    font-weight: 700;
    background-color: $color-surface-hover;
    color: $color-primary;
    padding: 3px 6px;
    border-radius: $radius-sm;
  }

  h4 {
    font-size: 14px;
    font-weight: 600;
  }

  .doc-counts {
    font-size: 12px;
    color: $color-text-secondary;
  }
}

.doc-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn {
  padding: 6px 12px;
  border-radius: $radius-md;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;

  &.btn-action {
    background-color: $color-surface-hover;
    color: $color-text-primary;
    border: 1px solid $color-border;
    &:hover {
      background-color: lighten(#334155, 5%);
    }
  }

  &.btn-danger {
    color: $color-status-missing;
    &:hover {
      background-color: $color-status-missing-bg;
    }
  }
}

.empty-docs {
  padding: 24px;
  background-color: $color-surface;
  border: 1px dashed $color-border;
  border-radius: $radius-md;
  text-align: center;
  color: $color-text-muted;
}
</style>