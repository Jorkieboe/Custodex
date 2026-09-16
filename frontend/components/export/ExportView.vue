<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { type ValidationBlocker, type SchemaField, fetchProjectSchema } from '../../services/api'

const store = useWorkspaceStore()
const activeTab = ref<'manifest' | 'metadata' | 'schema'>('manifest')
const isDownloading = ref(false)
const downloadError = ref<string | null>(null)
const projectSchema = ref<SchemaField[]>([])

const isValid = computed(() => store.validationResult?.is_valid === true)
const blockers = computed(() => store.validationResult?.blockers || [])
const summary = computed(() => store.validationResult?.summary || { empty_chunks: 0, uncalculated_embeddings: 0, schema_violations: 0 })
const totalChunks = computed(() => store.nodes.filter(n => n.node_type === 'paragraph').length)

onMounted(async () => {
  if (store.currentProject) {
    try {
      projectSchema.value = await fetchProjectSchema(store.currentProject.id)
    } catch {
      projectSchema.value = store.schemaFields
    }
  }
  await store.runValidation()
})

function handleJumpToNode(blocker: ValidationBlocker) {
  store.navigateToBlocker(blocker)
}

function handleResolveEmbeddings() {
  store.setStep('embeddings')
  store.refreshEmbeddingsStream()
}

async function handleDownload() {
  if (!isValid.value || isDownloading.value) return
  isDownloading.value = true
  downloadError.value = null
  try {
    await store.executeBundleDownload()
  } catch (err: any) {
    downloadError.value = err.message || 'Failed to download export bundle'
  } finally {
    isDownloading.value = false
  }
}

const sampleMetadataPreview = computed(() => {
  const paragraphNodes = store.nodes.filter(n => n.node_type === 'paragraph').slice(0, 3)
  const sampleEntries = paragraphNodes.map((chunk, idx) => {
    const metaObj: Record<string, any> = {}
    for (const f of store.schemaFields) {
      metaObj[f.field_slug] = f.field_type === 'array[string]' ? ['sample_tag'] : 'sample_value'
    }
    return {
      vector_index: idx,
      chunk_id: chunk.id,
      document_id: chunk.document_id,
      order_index: chunk.order_index,
      text_content: chunk.text_content.slice(0, 120) + (chunk.text_content.length > 120 ? '...' : ''),
      breadcrumb: 'Document > Section > Header',
      metadata: metaObj
    }
  })
  return JSON.stringify(sampleEntries, null, 2)
})

const compiledSchemaPreview = computed(() => {
  const properties: Record<string, any> = {}
  const required: string[] = []

  for (const field of store.schemaFields) {
    const slug = field.field_slug || `field_${field.id.slice(0, 8)}`
    const propDef: Record<string, any> = {}
    if (field.description) propDef.description = field.description

    if (field.field_type === 'string') propDef.type = 'string'
    else if (field.field_type === 'number') propDef.type = 'number'
    else if (field.field_type === 'boolean') propDef.type = 'boolean'
    else if (field.field_type === 'date') { propDef.type = 'string'; propDef.format = 'date' }
    else if (field.field_type === 'array[string]') { propDef.type = 'array'; propDef.items = { type: 'string' } }
    else if (field.field_type === 'array[number]') { propDef.type = 'array'; propDef.items = { type: 'number' } }

    properties[slug] = propDef
    if (field.is_required) required.push(slug)
  }

  const schema: Record<string, any> = {
    $schema: 'http://json-schema.org/draft-07/schema#',
    type: 'object',
    properties,
    additionalProperties: false
  }
  if (required.length > 0) schema.required = required
  return JSON.stringify(schema, null, 2)
})
</script>

<template>
  <div class="export-screen">
    <!-- Top Header Bar -->
    <header class="export-header">
      <div class="header-left">
        <h2>Validation Gate & RAG Bundle Exporter</h2>
        <p class="header-sub">Verify dataset completeness, inspect packaged artifacts, and generate production-ready RAG bundles.</p>
      </div>
      <div class="header-right">
        <button
          class="btn btn-secondary"
          :disabled="store.isValidating"
          @click="store.runValidation"
        >
          {{ store.isValidating ? 'Checking...' : '🔄 Re-run Validation' }}
        </button>
        <button
          class="btn btn-primary btn-export"
          :disabled="!isValid || isDownloading"
          @click="handleDownload"
        >
          {{ isDownloading ? 'Preparing ZIP...' : '📦 Download RAG Bundle (.ZIP)' }}
        </button>
      </div>
    </header>

    <!-- Error notice if download fails -->
    <div v-if="downloadError" class="alert-banner alert-error">
      <span>{{ downloadError }}</span>
      <button class="btn-close-alert" @click="downloadError = null">✕</button>
    </div>

    <!-- Main 2-Column Content Area -->
    <div class="export-body">
      <!-- Left Column: Validation Gate & Blockers -->
      <div class="column-validation">
        <!-- Status Card -->
        <div class="status-card" :class="isValid ? 'status-pass' : 'status-fail'">
          <div class="status-top">
            <span class="status-icon">{{ isValid ? '✅' : '⚠️' }}</span>
            <div class="status-info">
              <h3>{{ isValid ? 'All Validation Invariants Satisfied' : `Export Blocked: ${blockers.length} Issue(s) Detected` }}</h3>
              <p>
                {{ isValid
                  ? 'All text chunks are populated, embeddings are synchronized, and metadata matches the active schema contract.'
                  : 'The export gate blocks bundle creation until all chunks and metadata are concrete and verified.' }}
              </p>
            </div>
          </div>

          <!-- Metric Summary Pills -->
          <div class="metrics-grid">
            <div class="metric-item">
              <span class="metric-num">{{ totalChunks }}</span>
              <span class="metric-label">Total Chunks</span>
            </div>
            <div class="metric-item">
              <span class="metric-num" :class="{ 'text-error': summary.uncalculated_embeddings > 0 }">
                {{ store.currentEmbeddingCounts.current }} / {{ totalChunks }}
              </span>
              <span class="metric-label">Current Vectors</span>
            </div>
            <div class="metric-item">
              <span class="metric-num">{{ store.schemaFields.length }}</span>
              <span class="metric-label">Schema Fields</span>
            </div>
            <div class="metric-item">
              <span class="metric-num" :class="blockers.length === 0 ? 'text-success' : 'text-error'">
                {{ blockers.length }}
              </span>
              <span class="metric-label">Blockers</span>
            </div>
          </div>
        </div>

        <!-- Quick Remediation Action for Stale/Missing Embeddings -->
        <div v-if="summary.uncalculated_embeddings > 0" class="remediation-banner">
          <div class="remediation-text">
            <strong>{{ summary.uncalculated_embeddings }} chunk vector(s) require re-computation</strong>
            <p>Generate missing or stale embeddings to unblock export packaging.</p>
          </div>
          <button class="btn btn-warning" @click="handleResolveEmbeddings">
            ⚡ Refresh Stale Embeddings
          </button>
        </div>

        <!-- Blocker List Section -->
        <div v-if="blockers.length > 0" class="blockers-section">
          <div class="section-title-row">
            <h4>Concrete Remediation Items ({{ blockers.length }})</h4>
            <div class="blocker-summary-chips">
              <span v-if="summary.empty_chunks > 0" class="chip chip-empty">{{ summary.empty_chunks }} Empty</span>
              <span v-if="summary.uncalculated_embeddings > 0" class="chip chip-embeddings">{{ summary.uncalculated_embeddings }} Embeddings</span>
              <span v-if="summary.schema_violations > 0" class="chip chip-schema">{{ summary.schema_violations }} Schema</span>
            </div>
          </div>

          <div class="blockers-list">
            <div
              v-for="(blocker, idx) in blockers"
              :key="`${blocker.node_id}_${idx}`"
              class="blocker-item"
            >
              <div class="blocker-content">
                <div class="blocker-meta">
                  <span class="rule-badge" :class="`rule-${blocker.rule}`">
                    {{ blocker.rule.replace('_', ' ').toUpperCase() }}
                  </span>
                  <span class="blocker-doc">{{ blocker.filename }}</span>
                  <span class="blocker-node-id">Chunk: {{ blocker.node_id.slice(0, 8) }}</span>
                </div>
                <p class="blocker-message">{{ blocker.message }}</p>
                <span class="blocker-guide">💡 {{ blocker.remediation }}</span>
              </div>
              <button class="btn btn-sm btn-jump" @click="handleJumpToNode(blocker)">
                Jump to Chunk →
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Bundle Artifacts Preview -->
      <div class="column-artifacts">
        <div class="artifacts-container">
          <!-- Artifact Tabs -->
          <div class="artifacts-tabs">
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'manifest' }"
              @click="activeTab = 'manifest'"
            >
              📦 Bundle Manifest
            </button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'metadata' }"
              @click="activeTab = 'metadata'"
            >
              📄 dbmetadata.json
            </button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'schema' }"
              @click="activeTab = 'schema'"
            >
              📐 metadatascheme.json
            </button>
          </div>

          <!-- Tab Content 1: Manifest Overview -->
          <div v-if="activeTab === 'manifest'" class="tab-pane manifest-pane">
            <div class="manifest-card">
              <div class="artifact-row">
                <span class="artifact-icon">⚡</span>
                <div class="artifact-info">
                  <h5>db.faiss</h5>
                  <p>Serialized FAISS Flat Inner Product index mapping normalized vectors directly to chunk UUID sequences.</p>
                  <span class="artifact-meta">{{ store.currentEmbeddingCounts.current }} vectors indexed</span>
                </div>
              </div>
              <div class="artifact-row">
                <span class="artifact-icon">📄</span>
                <div class="artifact-info">
                  <h5>dbmetadata.json</h5>
                  <p>Sequential chunk records with contextual breadcrumb hierarchies, raw texts, document order, and extracted metadata.</p>
                  <span class="artifact-meta">{{ totalChunks }} chunk records</span>
                </div>
              </div>
              <div class="artifact-row">
                <span class="artifact-icon">📐</span>
                <div class="artifact-info">
                  <h5>metadatascheme.json</h5>
                  <p>Self-describing JSON Schema contract defining the metadata fields, types, and constraints for retrieval consumers.</p>
                  <span class="artifact-meta">{{ store.schemaFields.length }} attribute definitions</span>
                </div>
              </div>
            </div>

            <div class="bundle-footer-note">
              <span class="note-label">Target Bundle Archive:</span>
              <code>{{ (store.currentProject?.name.toLowerCase().replace(/\s+/g, '_') || 'project') }}-rag-bundle.zip</code>
            </div>
          </div>

          <!-- Tab Content 2: dbmetadata.json Preview -->
          <div v-else-if="activeTab === 'metadata'" class="tab-pane code-pane">
            <div class="pane-header-info">
              <span>Preview of chunk mapping format:</span>
            </div>
            <pre class="code-preview"><code>{{ sampleMetadataPreview }}</code></pre>
          </div>

          <!-- Tab Content 3: metadatascheme.json Preview -->
          <div v-else-if="activeTab === 'schema'" class="tab-pane code-pane">
            <div class="pane-header-info">
              <span>Compiled JSON Schema specification:</span>
            </div>
            <pre class="code-preview"><code>{{ compiledSchemaPreview }}</code></pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.export-screen {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: calc(100vh - #{$header-height});
  background-color: $color-bg;
  overflow: hidden;
}

.export-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 28px;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  flex-shrink: 0;
}

.header-left {
  h2 {
    font-size: 18px;
    font-weight: 700;
  }
  .header-sub {
    font-size: 12px;
    color: $color-text-secondary;
    margin-top: 2px;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alert-banner {
  padding: 10px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;

  &.alert-error {
    background-color: rgba(239, 68, 68, 0.15);
    border-bottom: 1px solid $color-status-missing;
    color: $color-status-missing;
  }

  .btn-close-alert {
    background: none;
    border: none;
    color: inherit;
    font-size: 14px;
    cursor: pointer;
  }
}

.export-body {
  flex: 1;
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  overflow: hidden;
}

.column-validation {
  padding: 24px 28px;
  overflow-y: auto;
  border-right: 1px solid $color-border;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.status-card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;

  &.status-pass {
    border-color: rgba(34, 197, 94, 0.4);
    background: linear-gradient(180deg, rgba(34, 197, 94, 0.05) 0%, rgba(30, 41, 59, 1) 100%);
  }

  &.status-fail {
    border-color: rgba(239, 68, 68, 0.4);
    background: linear-gradient(180deg, rgba(239, 68, 68, 0.05) 0%, rgba(30, 41, 59, 1) 100%);
  }
}

.status-top {
  display: flex;
  align-items: flex-start;
  gap: 14px;

  .status-icon {
    font-size: 28px;
    line-height: 1;
  }

  h3 {
    font-size: 16px;
    font-weight: 700;
  }

  p {
    font-size: 13px;
    color: $color-text-secondary;
    margin-top: 4px;
  }
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: $radius-md;
  padding: 8px 12px;

  .metric-num {
    font-family: $font-family-mono;
    font-size: 16px;
    font-weight: 700;
    color: $color-text-primary;

    &.text-success { color: $color-status-current; }
    &.text-error { color: $color-status-missing; }
  }

  .metric-label {
    font-size: 11px;
    color: $color-text-muted;
    margin-top: 2px;
  }
}

.remediation-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: rgba(234, 179, 8, 0.12);
  border: 1px solid rgba(234, 179, 8, 0.3);
  border-radius: $radius-md;
  padding: 14px 18px;

  strong {
    font-size: 13px;
    color: #facc15;
  }

  p {
    font-size: 12px;
    color: $color-text-secondary;
    margin-top: 2px;
  }
}

.blockers-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h4 {
    font-size: 14px;
    font-weight: 700;
    color: $color-text-primary;
  }
}

.blocker-summary-chips {
  display: flex;
  gap: 6px;

  .chip {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: $radius-sm;

    &.chip-empty { background-color: rgba(239, 68, 68, 0.2); color: $color-status-missing; }
    &.chip-embeddings { background-color: rgba(234, 179, 8, 0.2); color: $color-status-stale; }
    &.chip-schema { background-color: rgba(168, 85, 247, 0.2); color: #c084fc; }
  }
}

.blockers-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.blocker-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  padding: 12px 16px;
  gap: 16px;
}

.blocker-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.blocker-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;

  &.rule-empty_chunk { background-color: rgba(239, 68, 68, 0.2); color: $color-status-missing; }
  &.rule-uncalculated_embedding { background-color: rgba(234, 179, 8, 0.2); color: $color-status-stale; }
  &.rule-schema_violation { background-color: rgba(168, 85, 247, 0.2); color: #c084fc; }
}

.blocker-doc {
  font-size: 11px;
  font-weight: 600;
  color: $color-text-secondary;
}

.blocker-node-id {
  font-family: $font-family-mono;
  font-size: 10px;
  color: $color-text-muted;
}

.blocker-message {
  font-size: 13px;
  color: $color-text-primary;
}

.blocker-guide {
  font-size: 11px;
  color: $color-text-muted;
}

.column-artifacts {
  padding: 24px 28px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.artifacts-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  overflow: hidden;
}

.artifacts-tabs {
  display: flex;
  background-color: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid $color-border;
}

.tab-btn {
  padding: 10px 16px;
  font-size: 12px;
  font-weight: 600;
  color: $color-text-secondary;
  border-bottom: 2px solid transparent;
  transition: all 0.15s ease;

  &:hover {
    color: $color-text-primary;
  }

  &.active {
    color: $color-primary;
    border-bottom-color: $color-primary;
    background-color: rgba(255, 255, 255, 0.02);
  }
}

.tab-pane {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.manifest-pane {
  gap: 16px;
}

.manifest-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.artifact-row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 12px;
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid $color-border;
  border-radius: $radius-md;

  .artifact-icon {
    font-size: 20px;
    line-height: 1;
  }

  h5 {
    font-size: 14px;
    font-weight: 700;
    font-family: $font-family-mono;
    color: $color-primary;
  }

  p {
    font-size: 12px;
    color: $color-text-secondary;
    margin-top: 2px;
    line-height: 1.4;
  }

  .artifact-meta {
    display: inline-block;
    font-size: 11px;
    color: $color-text-muted;
    margin-top: 6px;
    font-family: $font-family-mono;
  }
}

.bundle-footer-note {
  margin-top: auto;
  padding: 12px 14px;
  background-color: rgba(56, 189, 248, 0.08);
  border: 1px dashed rgba(56, 189, 248, 0.3);
  border-radius: $radius-md;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;

  .note-label {
    color: $color-text-secondary;
  }

  code {
    font-family: $font-family-mono;
    font-weight: 700;
    color: $color-primary;
  }
}

.code-pane {
  gap: 10px;

  .pane-header-info {
    font-size: 11px;
    color: $color-text-muted;
  }
}

.code-preview {
  flex: 1;
  background-color: rgba(0, 0, 0, 0.35);
  border: 1px solid $color-border;
  border-radius: $radius-md;
  padding: 14px;
  font-family: $font-family-mono;
  font-size: 11px;
  color: #38bdf8;
  line-height: 1.45;
  overflow: auto;
}

.btn {
  padding: 8px 16px;
  border-radius: $radius-md;
  font-size: 13px;
  font-weight: 600;
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

  &.btn-warning {
    background-color: #facc15;
    color: #000;
    font-size: 12px;
    padding: 6px 14px;
    &:hover { background-color: #eab308; }
  }

  &.btn-jump {
    background-color: $color-surface-hover;
    color: $color-primary;
    border: 1px solid $color-border;
    font-size: 11px;
    padding: 5px 12px;
    border-radius: $radius-sm;
    white-space: nowrap;

    &:hover {
      border-color: $color-primary;
    }
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>