<script setup lang="ts">
import { computed } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { type ValidationBlocker } from '../../services/api'

const store = useWorkspaceStore()

const isValid = computed(() => store.validationResult?.is_valid === true)
const blockers = computed(() => store.validationResult?.blockers || [])
const summary = computed(() => store.validationResult?.summary || { empty_chunks: 0, uncalculated_embeddings: 0, schema_violations: 0 })

function handleJumpToNode(blocker: ValidationBlocker) {
  store.navigateToBlocker(blocker)
}

function handleResolveEmbeddings() {
  store.closeExportModal()
  store.setStep('embeddings')
  store.refreshEmbeddingsStream()
}

async function handleDownload() {
  await store.executeBundleDownload()
}
</script>

<template>
  <div v-if="store.isExportModalOpen" class="modal-backdrop">
    <div class="modal-card">
      <div class="modal-header">
        <div>
          <h3>Export RAG Scheme Bundle</h3>
          <span class="subtext">Pre-export validation gate evaluates all chunks before packaging</span>
        </div>
        <button class="btn-close" @click="store.closeExportModal" title="Close Modal">✕</button>
      </div>

      <div class="modal-body">
        <!-- Loading State -->
        <div v-if="store.isValidating" class="state-loading">
          <div class="spinner"></div>
          <p>Running integrity and schema validation checks...</p>
        </div>

        <!-- Valid State -->
        <div v-else-if="isValid" class="state-valid">
          <div class="valid-badge-icon">✅</div>
          <h4>Project Data is Concrete & Verified</h4>
          <p class="valid-desc">
            All {{ store.validationResult?.total_chunks }} chunks possess valid text content, up-to-date vector embeddings, and schema-compliant metadata attributes.
          </p>

          <div class="bundle-manifest">
            <span class="manifest-title">Bundle Artifacts:</span>
            <ul>
              <li><strong>db.faiss</strong> — Serialized FAISS CPU Flat index</li>
              <li><strong>dbmetadata.json</strong> — Sequential chunk mapping with breadcrumbs</li>
              <li><strong>metadatascheme.json</strong> — Self-describing active JSON Schema contract</li>
            </ul>
          </div>
        </div>

        <!-- Blocked State -->
        <div v-else class="state-blocked">
          <div class="blocked-header">
            <span class="blocked-icon">⚠️</span>
            <div>
              <h4>Export Blocked: {{ store.validationResult?.total_blockers }} Issues Found</h4>
              <p class="blocked-desc">Resolve the following items before generating the final RAG bundle.</p>
            </div>
          </div>

          <!-- Summary Badges -->
          <div class="summary-chips">
            <span v-if="summary.empty_chunks > 0" class="chip chip-empty">
              {{ summary.empty_chunks }} Empty Chunks
            </span>
            <span v-if="summary.uncalculated_embeddings > 0" class="chip chip-embeddings">
              {{ summary.uncalculated_embeddings }} Stale/Missing Embeddings
            </span>
            <span v-if="summary.schema_violations > 0" class="chip chip-schema">
              {{ summary.schema_violations }} Schema Violations
            </span>
          </div>

          <!-- Quick Remediation Button for Vectors -->
          <div v-if="summary.uncalculated_embeddings > 0" class="remediation-bar">
            <span>Needs vector re-computation:</span>
            <button class="btn btn-action" @click="handleResolveEmbeddings">
              ⚡ Generate All Missing/Stale Embeddings
            </button>
          </div>

          <!-- Blocker List -->
          <div class="blocker-list">
            <div
              v-for="(blocker, idx) in blockers"
              :key="`${blocker.node_id}_${idx}`"
              class="blocker-card"
            >
              <div class="blocker-info">
                <div class="blocker-title-row">
                  <span class="rule-badge" :class="`rule-${blocker.rule}`">
                    {{ blocker.rule.replace('_', ' ').toUpperCase() }}
                  </span>
                  <span class="doc-badge">{{ blocker.filename }}</span>
                  <span class="node-id-badge">ID: {{ blocker.node_id.slice(0, 8) }}</span>
                </div>
                <p class="blocker-msg">{{ blocker.message }}</p>
                <span class="blocker-remedy">👉 {{ blocker.remediation }}</span>
              </div>

              <button class="btn btn-jump" @click="handleJumpToNode(blocker)">
                Jump to Chunk
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button
          v-if="!isValid"
          class="btn btn-secondary"
          :disabled="store.isValidating"
          @click="store.runValidation"
        >
          🔄 Re-validate
        </button>

        <button
          v-if="isValid"
          class="btn btn-primary"
          @click="handleDownload"
        >
          📦 Download RAG Bundle (.ZIP)
        </button>

        <button class="btn btn-secondary" @click="store.closeExportModal">
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
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  width: 620px;
  max-height: 85vh;
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
}

.modal-header {
  padding: 18px 24px;
  border-bottom: 1px solid $color-border;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;

  h3 {
    font-size: 17px;
    font-weight: 700;
  }

  .subtext {
    font-size: 12px;
    color: $color-text-muted;
  }

  .btn-close {
    background: transparent;
    color: $color-text-muted;
    font-size: 16px;
    &:hover { color: $color-text-primary; }
  }
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.state-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 0;
  color: $color-text-secondary;
  font-size: 13px;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: $color-primary;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.state-valid {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 10px;

  .valid-badge-icon {
    font-size: 38px;
  }

  h4 {
    font-size: 17px;
    font-weight: 700;
    color: $color-status-current;
  }

  .valid-desc {
    font-size: 13px;
    color: $color-text-secondary;
    max-width: 480px;
  }
}

.bundle-manifest {
  margin-top: 14px;
  background-color: rgba(0, 0, 0, 0.25);
  border: 1px solid $color-border;
  border-radius: $radius-md;
  padding: 14px 18px;
  width: 100%;
  text-align: left;

  .manifest-title {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    color: $color-text-muted;
  }

  ul {
    margin-top: 8px;
    padding-left: 20px;
    font-size: 13px;
    color: $color-text-primary;

    li {
      margin-bottom: 4px;
    }
  }
}

.state-blocked {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.blocked-header {
  display: flex;
  align-items: center;
  gap: 12px;

  .blocked-icon {
    font-size: 28px;
  }

  h4 {
    font-size: 16px;
    font-weight: 700;
    color: $color-status-missing;
  }

  .blocked-desc {
    font-size: 12px;
    color: $color-text-secondary;
  }
}

.summary-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;

  .chip {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: $radius-sm;

    &.chip-empty {
      background-color: rgba(248, 113, 113, 0.15);
      color: $color-status-missing;
    }
    &.chip-embeddings {
      background-color: rgba(250, 204, 21, 0.15);
      color: $color-status-stale;
    }
    &.chip-schema {
      background-color: rgba(168, 85, 247, 0.15);
      color: #c084fc;
    }
  }
}

.remediation-bar {
  background-color: rgba(250, 204, 21, 0.1);
  border: 1px solid rgba(250, 204, 21, 0.25);
  border-radius: $radius-sm;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: $color-text-primary;
}

.btn-action {
  background-color: $color-primary;
  color: #000;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: $radius-sm;
  cursor: pointer;
}

.blocker-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 280px;
  overflow-y: auto;
}

.blocker-card {
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid $color-border;
  border-radius: $radius-sm;
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.blocker-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.blocker-title-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.rule-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 0;

  &.rule-empty_chunk { background-color: rgba(248, 113, 113, 0.2); color: $color-status-missing; }
  &.rule-uncalculated_embedding { background-color: rgba(250, 204, 21, 0.2); color: $color-status-stale; }
  &.rule-schema_violation { background-color: rgba(168, 85, 247, 0.2); color: #c084fc; }
}

.doc-badge {
  font-size: 11px;
  color: $color-text-secondary;
}

.node-id-badge {
  font-family: $font-family-mono;
  font-size: 10px;
  color: $color-text-muted;
}

.blocker-msg {
  font-size: 12px;
  color: $color-text-primary;
}

.blocker-remedy {
  font-size: 11px;
  color: $color-text-muted;
}

.btn-jump {
  background-color: $color-surface-hover;
  color: $color-text-primary;
  border: 1px solid $color-border;
  font-size: 11px;
  padding: 5px 10px;
  border-radius: $radius-sm;
  white-space: nowrap;
  cursor: pointer;

  &:hover {
    border-color: $color-primary;
    color: $color-primary;
  }
}

.modal-footer {
  padding: 14px 24px;
  border-top: 1px solid $color-border;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
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