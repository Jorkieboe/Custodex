<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace.ts'
import { type NodeItem, type SchemaField } from '../services/api'
import HeaderOutlineLegend from '../components/canvas/HeaderOutlineLegend.vue'
import ActionBar from '../components/ActionBar.vue'
import HeaderNodeView from '../components/canvas/HeaderNodeView.vue'
import ChunkNodeView from '../components/canvas/ChunkNodeView.vue'

const store = useWorkspaceStore()

const fieldValues = ref<Record<string, any>>({})
let saveTimeouts: Record<string, ReturnType<typeof setTimeout>> = {}

const activeNode = computed<NodeItem | null>(() => {
  if (!store.activeNodeId) return null
  return store.nodes.find((n: NodeItem) => n.id === store.activeNodeId) || null
})

const activeHasMetadata = computed<boolean>(() => {
  if (!store.activeNodeId) return false
  if (store.nodesWithMetadata.has(store.activeNodeId)) return true
  return store.isNodeFullyExtracted(store.activeNodeMetadata, store.schemaFields)
})

const paragraphNodes = computed<NodeItem[]>(() => {
  return store.nodes.filter((n: NodeItem) => n.node_type === 'paragraph')
})

const headerChildCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const node of store.nodes) {
    if (node.node_type === 'paragraph' && node.parent_id) {
      counts[node.parent_id] = (counts[node.parent_id] || 0) + 1
    }
  }
  return counts
})

function canMerge(index: number): boolean {
  if (index >= store.nodes.length - 1) return false
  const current = store.nodes[index]
  const next = store.nodes[index + 1]
  return current.node_type === 'paragraph' && next.node_type === 'paragraph'
}

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

function handleStartAutogeneration() {
  store.startAutogeneration({ force_overwrite: store.metadataForceOverwrite })
}

async function handlePrimaryButtonAction() {
  if (!store.activeNodeId) return
  console.log(`[Custodex Metadata] Regenerating metadata for selected chunk ${store.activeNodeId}`)
  await store.generateMetadataForNode(store.activeNodeId)
  console.log(`[Custodex Metadata Output] Final fields:`, fieldValues.value)
}

</script>

<template>
  <div class="metadata-view-container">
    <!-- Shared Context-Aware Action Bar -->
    <ActionBar />

    <!-- Error Banner if Batch Job Failed -->
    <div v-if="store.metadataJobStatus.status === 'failed' && store.metadataJobStatus.last_error" class="error-banner">
      <span>Extraction interrupted: {{ store.metadataJobStatus.last_error }}</span>
      <button class="btn btn-retry" @click="handleStartAutogeneration">
        Resume Extraction
      </button>
    </div>

    <!-- Main 3-Column Display: 20% headeroutline, 60% chunks, 20% metadata input -->
    <main class="metadata-main">
      <!-- Column 1: Header Outline (20%) -->
      <HeaderOutlineLegend />

      <!-- Column 2: Chunks (60%) -->
      <div class="chunks-scroll-area canvas-scroll-container">
        <div v-if="paragraphNodes.length === 0" class="empty-chunks">
          No text chunks available. Ingest documents to populate content.
        </div>

        <div v-else class="nodes-list">
          <template v-for="(node, index) in store.nodes" :key="node.id">
            <HeaderNodeView
              v-if="node.node_type === 'header'"
              :node="node"
              :child-count="headerChildCounts[node.id] || 0"
              @demote="id => store.demoteNode(id)"
            />
            <ChunkNodeView
              v-else
              :node="node"
              :can-merge="canMerge(index)"
              @split="(id, top, bot) => store.splitNode(id, top, bot)"
              @merge="id => store.mergeNode(id)"
              @promote="id => store.promoteNode(id)"
            />
          </template>
        </div>
      </div>

      <!-- Column 3: Metadata Form (20%) -->
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
@use '../styles/variables' as *;

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
  border-radius: 0;
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
  display: grid;
  grid-template-columns: 20% 60% 20%;
  overflow: hidden;

  > :first-child {
    min-width: 0;
    overflow-y: auto;
  }
}

.chunks-scroll-area {
  min-width: 0;
  padding: 24px;
  overflow-y: auto;
  border-right: 1px solid $color-border;
}

.empty-chunks {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: $color-text-muted;
  font-size: 14px;
}

.nodes-list {
  max-width: 860px;
  margin: 0 auto;
}

.right-column {
  min-width: 0;
  background-color: rgba(0, 0, 0, 0.1);
  padding: 24px 16px;
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
  font-size: 16px;
  font-weight: 600;
  padding: 8px 16px;
  border-radius: 0;
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