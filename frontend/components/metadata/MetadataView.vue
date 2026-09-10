<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { type NodeItem, type SchemaField } from '../../services/api'

const store = useWorkspaceStore()

const forceOverwrite = ref(false)
const fieldValues = ref<Record<string, any>>({})
let saveTimeouts: Record<string, ReturnType<typeof setTimeout>> = {}

const activeNode = computed<NodeItem | null>(() => {
  if (!store.activeNodeId) return null
  return store.nodes.find((n: NodeItem) => n.id === store.activeNodeId) || null
})

const activeHasMetadata = computed<boolean>(() => {
  if (!store.activeNodeId) return false
  if (store.nodesWithMetadata.has(store.activeNodeId)) return true
  if (!store.activeNodeMetadata || store.activeNodeMetadata.length === 0) return false
  return store.activeNodeMetadata.every((item) => {
    if (item.field_value === null || item.field_value === undefined) return false
    if (typeof item.field_value === 'string' && item.field_value.trim() === '') return false
    if (Array.isArray(item.field_value) && item.field_value.length === 0) return false
    return true
  })
})

const paragraphNodes = computed<NodeItem[]>(() => {
  return store.nodes.filter((n: NodeItem) => n.node_type === 'paragraph')
})

const groupedByHeaders = computed(() => {
  const groups: { header: NodeItem | null; chunks: NodeItem[] }[] = []
  let currentHeader: NodeItem | null = null
  let currentChunks: NodeItem[] = []

  for (const node of store.nodes) {
    if (node.node_type === 'header') {
      if (currentHeader !== null || currentChunks.length > 0) {
        groups.push({ header: currentHeader, chunks: currentChunks })
      }
      currentHeader = node
      currentChunks = []
    } else {
      currentChunks.push(node)
    }
  }

  if (currentHeader !== null || currentChunks.length > 0) {
    groups.push({ header: currentHeader, chunks: currentChunks })
  }

  return groups
})

const documentPalette: string[] = [
  '#fecdd3', // soft pink
  '#d1fae5', // soft emerald
  '#dbeafe', // soft blue
  '#fef3c7', // soft amber
  '#e0e7ff'  // soft indigo
]

const documentColorMap = computed(() => {
  const map: Record<string, string> = {}
  store.documents.forEach((doc, idx) => {
    map[doc.id] = documentPalette[idx % documentPalette.length]
  })
  return map
})

onMounted(async () => {
  await store.reloadSchema()
  if (paragraphNodes.value.length > 0 && !store.activeNodeId) {
    await store.selectNode(paragraphNodes.value[0].id)
  }
  store.loadProjectMetadataOverview()
})

watch(
  () => store.activeNodeMetadata,
  (newMetadata) => {
    const nextValues: Record<string, any> = {}
    for (const item of newMetadata) {
      nextValues[item.field_id] = item.field_value
    }
    fieldValues.value = nextValues
    if (newMetadata && newMetadata.length > 0) {
      console.log(`[Custodex Metadata Output] Node: ${store.activeNodeId}`, nextValues)
    }
  },
  { immediate: true, deep: true }
)

function handleSelectChunk(nodeId: string) {
  store.selectNode(nodeId)
}

function handleFieldValueChange(fieldId: string, value: any) {
  fieldValues.value[fieldId] = value

  if (!store.activeNodeId) return
  const targetNodeId = store.activeNodeId

  if (saveTimeouts[fieldId]) {
    clearTimeout(saveTimeouts[fieldId])
  }

  saveTimeouts[fieldId] = setTimeout(() => {
    store.saveNodeMetadataField(targetNodeId, fieldId, value)
    store.nodesWithMetadata.add(targetNodeId)
  }, 400)
}

function handleArrayFieldChange(fieldId: string, event: Event) {
  const raw = (event.target as HTMLInputElement).value
  const items = raw.split(',').map(s => s.trim()).filter(Boolean)
  handleFieldValueChange(fieldId, items)
}

async function handleGenerateForChunk(nodeId: string) {
  console.log(`[Custodex Metadata] Triggering single chunk generation for node ${nodeId}`)
  await store.selectNode(nodeId)
  await store.generateMetadataForNode(nodeId)
  console.log(`[Custodex Metadata Output] Generated for ${nodeId}:`, fieldValues.value)
}

async function handlePrimaryButtonAction() {
  if (!store.activeNodeId) return
  console.log(`[Custodex Metadata] Regenerating metadata for selected chunk ${store.activeNodeId}`)
  await store.generateMetadataForNode(store.activeNodeId)
  console.log(`[Custodex Metadata Output] Final fields:`, fieldValues.value)
}

function handleStartAutogeneration() {
  store.startAutogeneration({ force_overwrite: forceOverwrite.value })
}

function handleCancelAutogeneration() {
  store.cancelAutogeneration()
}

const progressPercentage = computed(() => {
  const { completed_chunks, total_chunks } = store.metadataJobStatus
  if (!total_chunks || total_chunks === 0) return 0
  return Math.min(100, Math.round((completed_chunks / total_chunks) * 100))
})
</script>

<template>
  <div class="metadata-view-container">
    <!-- Top Action Bar: Option to start autogeneration -->
    <header class="autogeneration-bar">
      <div class="autogen-left">
        <div class="title-wrap">
          <span class="sparkle-icon">✨</span>
          <span class="bar-title">Metadata Extraction Engine</span>
        </div>

        <div class="autogen-controls" v-if="store.metadataJobStatus.status !== 'running'">
          <label class="force-toggle">
            <input v-model="forceOverwrite" type="checkbox" />
            <span>Force Overwrite User Edits</span>
          </label>

          <button class="btn btn-autogen" @click="handleStartAutogeneration">
            ▶ Start Autogeneration (All Chunks)
          </button>
        </div>

        <!-- Real-time SSE Progress Mode -->
        <div class="sse-progress-panel" v-else>
          <div class="sse-indicator">
            <span class="pulse-dot"></span>
            <span class="status-label">Extracting Metadata via SSE...</span>
          </div>

          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${progressPercentage}%` }"></div>
          </div>

          <span class="progress-numbers">
            {{ store.metadataJobStatus.completed_chunks }} / {{ store.metadataJobStatus.total_chunks }} chunks ({{ progressPercentage }}%)
          </span>

          <span class="partition-badge" v-if="store.metadataJobStatus.total_partitions > 1">
            Part {{ store.metadataJobStatus.completed_partitions + 1 }} of {{ store.metadataJobStatus.total_partitions }}
          </span>

          <button class="btn btn-cancel" @click="handleCancelAutogeneration">
            Stop
          </button>
        </div>
      </div>

      <div class="autogen-right">
        <span class="stat-pill">
          Chunks with metadata: {{ store.nodesWithMetadata.size }} / {{ paragraphNodes.length }}
        </span>
      </div>
    </header>

    <!-- Error Banner if Batch Job Failed -->
    <div v-if="store.metadataJobStatus.status === 'failed' && store.metadataJobStatus.last_error" class="error-banner">
      <span>Extraction interrupted: {{ store.metadataJobStatus.last_error }}</span>
      <button class="btn btn-retry" @click="handleStartAutogeneration">
        Resume Extraction
      </button>
    </div>

    <!-- Main 2-Column Display -->
    <main class="metadata-main">
      <!-- Left Column: Document Tree + Chunks -->
      <section class="left-column">
        <!-- Far-Left Document Tree Sidebar (from mockup) -->
        <aside class="hierarchy-sidebar">
          <div class="sidebar-title">Structure</div>
          <div class="sidebar-tree">
            <div
              v-for="doc in store.documents"
              :key="doc.id"
              class="tree-doc-group"
            >
              <div
                class="tree-pill doc-pill"
                :style="{ backgroundColor: documentColorMap[doc.id] || '#dbeafe' }"
                :title="doc.filename"
              >
                ^ {{ doc.filename.length > 14 ? doc.filename.slice(0, 14) + '...' : doc.filename }}
              </div>

              <div class="header-nodes-sublist">
                <div
                  v-for="node in store.nodes.filter(n => n.document_id === doc.id && n.node_type === 'header')"
                  :key="node.id"
                  class="tree-pill header-pill"
                  :style="{ backgroundColor: documentColorMap[doc.id] || '#dbeafe' }"
                  :title="node.text_content"
                >
                  {{ node.text_content.length > 16 ? node.text_content.slice(0, 16) + '...' : node.text_content }}
                </div>
              </div>
            </div>
          </div>
        </aside>

        <!-- Chunks Canvas (Left/Center) -->
        <div class="chunks-scroll-area">
          <div v-if="paragraphNodes.length === 0" class="empty-chunks">
            No text chunks available. Ingest documents to populate content.
          </div>

          <div v-else class="grouped-chunks-list">
            <div
              v-for="(group, gIdx) in groupedByHeaders"
              :key="gIdx"
              class="chunk-group"
            >
              <h3 v-if="group.header" class="group-header-title">
                {{ group.header.text_content }}
              </h3>

              <div class="group-items">
                <div
                  v-for="chunk in group.chunks"
                  :key="chunk.id"
                  class="chunk-card"
                  :class="{
                    active: store.activeNodeId === chunk.id,
                    'has-metadata': store.nodesWithMetadata.has(chunk.id)
                  }"
                  @click="handleSelectChunk(chunk.id)"
                >
                  <div class="chunk-card-meta">
                    <span class="chunk-index">#{{ chunk.order_index }}</span>
                    <span
                      v-if="store.nodesWithMetadata.has(chunk.id)"
                      class="badge-has-meta"
                    >
                      ✓ Extracted
                    </span>
                  </div>

                  <p class="chunk-text">
                    {{ chunk.text_content }}
                  </p>

                  <!-- Left-part Generate button if chunk has no metadata yet -->
                  <div
                    v-if="!store.nodesWithMetadata.has(chunk.id)"
                    class="chunk-generate-action"
                  >
                    <button
                      class="btn-chunk-generate"
                      :disabled="store.isGeneratingSingle === chunk.id"
                      @click.stop="handleGenerateForChunk(chunk.id)"
                    >
                      {{ store.isGeneratingSingle === chunk.id ? 'Generating...' : 'Generate' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Right Column: Metadata Form -->
      <section class="right-column">
        <div v-if="!activeNode" class="no-selection-card">
          <p>Select a chunk on the left to inspect and edit its metadata.</p>
        </div>

        <div v-else class="form-container">
          <!-- Large Top Action Button (Regenerate / Generate) -->
          <div class="regenerate-btn-wrap">
            <button
              class="btn-large-regenerate"
              :disabled="store.isGeneratingSingle === activeNode.id"
              @click="handlePrimaryButtonAction"
            >
              {{ store.isGeneratingSingle === activeNode.id
                ? 'Generating...'
                : (activeHasMetadata ? 'Regenerate' : 'Generate') }}
            </button>
          </div>

          <div v-if="store.schemaFields.length === 0" class="empty-schema-notice">
            <p>No schema fields defined yet.</p>
            <button class="btn btn-sm btn-primary" @click="store.setStep('schema')">
              Open Schema Designer
            </button>
          </div>

          <!-- Dynamic Form Fields from CMS Schema -->
          <form v-else class="fields-form" @submit.prevent>
            <div
              v-for="field in store.schemaFields"
              :key="field.id"
              class="form-field-group"
            >
              <label class="field-label">
                <span>{{ field.field_label || field.field_slug }}:</span>
                <span v-if="field.is_required" class="required-star">*</span>
                <span class="field-type-tag">{{ field.field_type }}</span>
              </label>

              <!-- Field description helper if available -->
              <span v-if="field.description" class="field-help">
                {{ field.description }}
              </span>

              <!-- String field input -->
              <input
                v-if="field.field_type === 'string'"
                type="text"
                class="form-input"
                :value="fieldValues[field.id] || ''"
                :placeholder="`Enter ${field.field_label.toLowerCase()}...`"
                @input="e => handleFieldValueChange(field.id, (e.target as HTMLInputElement).value)"
              />

              <!-- Number field input -->
              <input
                v-else-if="field.field_type === 'number'"
                type="number"
                class="form-input"
                :value="fieldValues[field.id] ?? ''"
                @input="e => handleFieldValueChange(field.id, parseFloat((e.target as HTMLInputElement).value))"
              />

              <!-- Boolean toggle input -->
              <div v-else-if="field.field_type === 'boolean'" class="toggle-wrap">
                <label class="switch-label">
                  <input
                    type="checkbox"
                    :checked="Boolean(fieldValues[field.id])"
                    @change="e => handleFieldValueChange(field.id, (e.target as HTMLInputElement).checked)"
                  />
                  <span>{{ fieldValues[field.id] ? 'True' : 'False' }}</span>
                </label>
              </div>

              <!-- Array string input (comma-delimited) -->
              <input
                v-else-if="field.field_type === 'array[string]'"
                type="text"
                class="form-input"
                :value="Array.isArray(fieldValues[field.id]) ? fieldValues[field.id].join(', ') : (fieldValues[field.id] || '')"
                placeholder="Comma-separated items (e.g. Alice, Bob, Charlie)..."
                @input="e => handleArrayFieldChange(field.id, e)"
              />

              <!-- Date field input -->
              <input
                v-else-if="field.field_type === 'date'"
                type="date"
                class="form-input"
                :value="fieldValues[field.id] || ''"
                @input="e => handleFieldValueChange(field.id, (e.target as HTMLInputElement).value)"
              />

              <!-- Fallback text input -->
              <input
                v-else
                type="text"
                class="form-input"
                :value="typeof fieldValues[field.id] === 'object' ? JSON.stringify(fieldValues[field.id]) : (fieldValues[field.id] || '')"
                @input="e => handleFieldValueChange(field.id, (e.target as HTMLInputElement).value)"
              />
            </div>
          </form>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.metadata-view-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - #{$header-height});
  background-color: $color-bg;
  overflow: hidden;
}

.autogeneration-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 24px;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  flex-shrink: 0;
}

.autogen-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;

  .sparkle-icon {
    font-size: 16px;
  }

  .bar-title {
    font-weight: 700;
    font-size: 14px;
    color: $color-text-primary;
  }
}

.autogen-controls {
  display: flex;
  align-items: center;
  gap: 16px;
}

.force-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: $color-text-secondary;
  cursor: pointer;

  input {
    accent-color: $color-primary;
  }
}

.btn-autogen {
  background-color: $color-primary;
  color: #000;
  font-weight: 600;
  font-size: 12px;
  padding: 6px 14px;
  border-radius: $radius-md;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background-color: $color-primary-hover;
  }
}

.sse-progress-panel {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sse-indicator {
  display: flex;
  align-items: center;
  gap: 6px;

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: $color-primary;
    box-shadow: 0 0 8px $color-primary;
    animation: pulse 1.2s infinite ease-in-out;
  }

  .status-label {
    font-size: 12px;
    font-weight: 600;
    color: $color-primary;
  }
}

@keyframes pulse {
  0%, 100% { transform: scale(0.9); opacity: 0.6; }
  50% { transform: scale(1.3); opacity: 1; }
}

.progress-track {
  width: 140px;
  height: 8px;
  background-color: rgba(0, 0, 0, 0.4);
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: $color-primary;
  transition: width 0.2s ease;
}

.progress-numbers {
  font-size: 12px;
  font-family: $font-family-mono;
  color: $color-text-secondary;
}

.partition-badge {
  font-size: 10px;
  font-weight: 700;
  background-color: $color-surface-hover;
  color: $color-text-primary;
  padding: 2px 6px;
  border-radius: $radius-sm;
}

.btn-cancel {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: $radius-sm;
  background-color: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
  cursor: pointer;

  &:hover {
    background-color: rgba(239, 68, 68, 0.3);
  }
}

.autogen-right {
  display: flex;
  align-items: center;
}

.stat-pill {
  font-size: 11px;
  font-family: $font-family-mono;
  color: $color-text-muted;
  background-color: rgba(0, 0, 0, 0.2);
  padding: 4px 10px;
  border-radius: $radius-sm;
}

.error-banner {
  background-color: rgba(239, 68, 68, 0.15);
  border-bottom: 1px solid #ef4444;
  color: #ef4444;
  font-size: 12px;
  padding: 8px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .btn-retry {
    padding: 4px 10px;
    background-color: #ef4444;
    color: #fff;
    border-radius: $radius-sm;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
  }
}

.metadata-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.left-column {
  flex: 1.2;
  display: flex;
  border-right: 1px solid $color-border;
  overflow: hidden;
}

.hierarchy-sidebar {
  width: 140px;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  background-color: rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  padding: 12px 8px;
  overflow-y: auto;
}

.sidebar-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: $color-text-muted;
  margin-bottom: 8px;
  padding-left: 4px;
}

.sidebar-tree {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tree-doc-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tree-pill {
  font-size: 11px;
  color: #1e293b;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: $radius-sm;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: default;
  user-select: none;
}

.header-nodes-sublist {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 8px;

  .header-pill {
    opacity: 0.85;
    font-size: 10px;
    font-weight: 500;
  }
}

.chunks-scroll-area {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.empty-chunks {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: $color-text-muted;
  font-size: 14px;
}

.grouped-chunks-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 600px;
}

.group-header-title {
  font-size: 15px;
  font-weight: 700;
  color: $color-text-primary;
  margin-bottom: 8px;
}

.group-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-card {
  background-color: #dbe4ff;
  color: #1e293b;
  border-radius: $radius-md;
  padding: 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 2px solid transparent;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &.active {
    border-color: #f59e0b;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.3);
  }
}

.chunk-card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.chunk-index {
  font-family: $font-family-mono;
  font-size: 10px;
  font-weight: 700;
  background-color: rgba(0, 0, 0, 0.1);
  padding: 1px 6px;
  border-radius: $radius-sm;
}

.badge-has-meta {
  font-size: 10px;
  font-weight: 700;
  color: #065f46;
  background-color: #a7f3d0;
  padding: 1px 6px;
  border-radius: $radius-sm;
}

.chunk-text {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.chunk-generate-action {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.btn-chunk-generate {
  background-color: #e69138;
  color: #ffffff;
  border-radius: $radius-sm;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 12px;
  cursor: pointer;
  transition: background-color 0.15s ease;

  &:hover:not(:disabled) {
    background-color: darken(#e69138, 8%);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.right-column {
  flex: 0.9;
  background-color: rgba(0, 0, 0, 0.1);
  padding: 32px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.no-selection-card {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: $color-text-muted;
  font-size: 14px;
  text-align: center;
}

.form-container {
  max-width: 480px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.regenerate-btn-wrap {
  display: flex;
  justify-content: flex-start;
}

.btn-large-regenerate {
  background-color: #e69138;
  color: #ffffff;
  font-size: 20px;
  font-weight: 600;
  padding: 12px 36px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);

  &:hover:not(:disabled) {
    background-color: darken(#e69138, 6%);
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.empty-schema-notice {
  background-color: $color-surface;
  border: 1px dashed $color-border;
  border-radius: $radius-md;
  padding: 24px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: $color-text-secondary;
}

.fields-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: $color-text-primary;
}

.required-star {
  color: #ef4444;
}

.field-type-tag {
  font-size: 10px;
  font-family: $font-family-mono;
  color: $color-text-muted;
  background-color: rgba(255, 255, 255, 0.05);
  padding: 1px 4px;
  border-radius: $radius-sm;
}

.field-help {
  font-size: 11px;
  color: $color-text-muted;
}

.form-input {
  background-color: #cbd5e1;
  color: #0f172a;
  border: none;
  border-radius: $radius-sm;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  transition: all 0.15s ease;

  &:focus {
    background-color: #ffffff;
    box-shadow: 0 0 0 2px $color-primary;
  }
}

.toggle-wrap {
  display: flex;
  align-items: center;
}

.switch-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;

  input {
    accent-color: #e69138;
    width: 16px;
    height: 16px;
  }
}

.btn {
  padding: 6px 12px;
  border-radius: $radius-md;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;

  &.btn-primary {
    background-color: $color-primary;
    color: #000;
    &:hover { background-color: $color-primary-hover; }
  }
}
</style>