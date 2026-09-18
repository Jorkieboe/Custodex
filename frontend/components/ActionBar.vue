<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const isAutoSplitting = ref(false)
const showBudgetPopup = ref(false)

const counts = computed(() => store.currentEmbeddingCounts)

const paragraphNodes = computed(() => {
  return store.nodes.filter((n) => n.node_type === 'paragraph')
})

const selectedParagraphCount = computed(() => {
  let count = 0
  for (const id of store.selectedNodeIds) {
    const node = store.nodes.find((n) => n.id === id)
    if (node && node.node_type === 'paragraph') {
      count++
    }
  }
  return count
})

async function handleBatchAutoSplit() {
  if (store.selectedNodeIds.size === 0) return
  isAutoSplitting.value = true
  try {
    const nodeIds = Array.from(store.selectedNodeIds)
    await store.requestSemanticSplitPreview(nodeIds)
  } finally {
    isAutoSplitting.value = false
  }
}

function handleStartMetadataAutogeneration() {
  if (store.selectedNodeIds.size > 0) {
    const selectedParagraphIds = Array.from(store.selectedNodeIds).filter((id) => {
      const node = store.nodes.find((n) => n.id === id)
      return node && node.node_type === 'paragraph'
    })
    store.startAutogeneration({
      force_overwrite: store.metadataForceOverwrite,
      node_ids: selectedParagraphIds.length > 0 ? selectedParagraphIds : undefined
    })
  } else {
    store.startAutogeneration({
      force_overwrite: store.metadataForceOverwrite
    })
  }
}

const progressPercentage = computed(() => {
  const { completed_chunks, total_chunks } = store.metadataJobStatus
  if (!total_chunks || total_chunks === 0) return 0
  return Math.min(100, Math.round((completed_chunks / total_chunks) * 100))
})
</script>

<template>
  <div v-if="store.nodes.length > 0" class="selection-action-bar">
    <!-- Left Section: Always displays Select All -->
    <div class="selection-left">
      <label class="select-all-label">
        <input
          type="checkbox"
          :checked="store.selectedNodeIds.size === store.nodes.length && store.nodes.length > 0"
          @change="$event => ($event.target as HTMLInputElement).checked ? store.selectAllNodes() : store.clearNodeSelection()"
        />
        <span>Select All ({{ store.selectedNodeIds.size }} / {{ store.nodes.length }})</span>
      </label>

      <!-- Context 1: Chunk Canvas Step -->
      <template v-if="store.currentStep === 'chunks'">
        <div v-if="store.selectedNodeIds.size > 0" class="batch-buttons">
          <button
            class="btn btn-sm btn-primary"
            :disabled="isAutoSplitting"
            @click="handleBatchAutoSplit"
          >
            {{ isAutoSplitting ? 'Analyzing...' : `⚡ Auto-Split (${store.selectedNodeIds.size})` }}
          </button>
          <button class="btn btn-sm btn-secondary" @click="store.clearNodeSelection">
            Deselect
          </button>
        </div>

        <div v-if="store.semanticSplitProposals.size > 0" class="proposals-toolbar-group">
          <span class="proposals-indicator">
            ⚡ {{ store.semanticSplitProposals.size }} chunk(s) have proposed splits
          </span>
          <button class="btn btn-sm btn-success" @click="store.acceptAllProposedSplits">
            ✓ Accept All Proposed Splits
          </button>
          <button class="btn btn-sm btn-secondary" @click="store.semanticSplitProposals.clear()">
            Dismiss Previews
          </button>
        </div>
      </template>

      <!-- Context 2: Metadata Extraction Step -->
      <template v-else-if="store.currentStep === 'metadata'">
        <div class="autogen-controls" v-if="store.metadataJobStatus.status !== 'running'">
          <label class="force-toggle">
            <input v-model="store.metadataForceOverwrite" type="checkbox" />
            <span>Force Overwrite User Edits</span>
          </label>

          <button class="btn btn-sm btn-autogen" @click="handleStartMetadataAutogeneration">
            {{ store.selectedNodeIds.size > 0
              ? `▶ Generate Selected (${selectedParagraphCount})`
              : '▶ Start Autogeneration (All Chunks)' }}
          </button>

          <button
            v-if="store.selectedNodeIds.size > 0"
            class="btn btn-sm btn-secondary"
            @click="store.clearNodeSelection"
          >
            Deselect
          </button>
        </div>

        <!-- SSE Progress Panel -->
        <div class="sse-progress-panel" v-else>
          <div class="sse-indicator">
            <span class="pulse-dot"></span>
            <span class="status-label">Extracting Metadata...</span>
          </div>

          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${progressPercentage}%` }"></div>
          </div>

          <span class="progress-numbers">
            {{ store.metadataJobStatus.completed_chunks }} / {{ store.metadataJobStatus.total_chunks }} ({{ progressPercentage }}%)
          </span>

          <button class="btn btn-sm btn-cancel" @click="store.cancelAutogeneration">
            Stop
          </button>
        </div>
      </template>

      <!-- Context 3: Embeddings Step (No auto-split button; has Deselect and action) -->
      <template v-else-if="store.currentStep === 'embeddings'">
        <div class="embedding-bar-left">
          

          <button
            v-if="store.selectedNodeIds.size > 0"
            class="btn btn-sm btn-secondary"
            @click="store.clearNodeSelection"
          >
            Deselect
          </button>
        </div>
      </template>
    </div>

    <!-- Right Section: Context Dependent Controls -->
    <div class="selection-right">
      <!-- Right Chunking Budget Popup on Chunk Canvas -->
      <div v-if="store.currentStep === 'chunks'" class="budget-popup-anchor">
        <button
          type="button"
          class="btn-selected-range"
          @click.stop="showBudgetPopup = !showBudgetPopup"
          title="Configure token range for auto-splitting"
        >
          <span>Selected Range: {{ store.autoSplitMinTokens }}–{{ store.autoSplitMaxTokens }} tok</span>
          <span class="range-chevron">{{ showBudgetPopup ? '▲' : '▼' }}</span>
        </button>

        <!-- Budget Pop-up Card -->
        <div
          v-if="showBudgetPopup"
          class="budget-popup-card"
          @click.stop
        >
          <div class="popup-header">
            <span class="popup-title">⚡ Chunk Token Budget</span>
            <button class="btn-close-popup" @click="showBudgetPopup = false">✕</button>
          </div>

          <div class="popup-section">
            <span class="section-label">Presets</span>
            <div class="preset-buttons">
              <button
                type="button"
                class="btn-preset"
                :class="{ active: store.autoSplitPreset === 'fine' }"
                @click="store.setAutoSplitRange(100, 150, 'fine')"
              >
                100–150 tok
              </button>
              <button
                type="button"
                class="btn-preset"
                :class="{ active: store.autoSplitPreset === 'standard' }"
                @click="store.setAutoSplitRange(200, 350, 'standard')"
              >
                200–350 tok
              </button>
              <button
                type="button"
                class="btn-preset"
                :class="{ active: store.autoSplitPreset === 'large' }"
                @click="store.setAutoSplitRange(400, 500, 'large')"
              >
                400–500 tok
              </button>
            </div>
          </div>

          <div class="popup-section">
            <span class="section-label">Custom Range</span>
            <div class="custom-token-inputs">
              <label>
                Min:
                <input
                  type="number"
                  v-model.number="store.autoSplitMinTokens"
                  min="20"
                  max="1500"
                  step="10"
                  @input="store.autoSplitPreset = 'custom'"
                />
              </label>
              <label>
                Max:
                <input
                  type="number"
                  v-model.number="store.autoSplitMaxTokens"
                  min="50"
                  max="2500"
                  step="10"
                  @input="store.autoSplitPreset = 'custom'"
                />
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Overview Stats for Metadata Step -->
      <div v-else-if="store.currentStep === 'metadata'" class="metadata-right-stat">
        <span class="stat-pill">
          Chunks with metadata: {{ store.nodesWithMetadata.size }} / {{ paragraphNodes.length }}
        </span>
      </div>

      <!-- Right Embedding Status Breakdown for Embeddings Step -->
      <div v-else-if="store.currentStep === 'embeddings'" class="embedding-right-breakdown">
        <div class="embedding-status-tags">
          <span class="emb-badge emb-current" title="Synchronized embeddings">
            Current: {{ counts.current }}
          </span>
          <span class="emb-badge emb-stale" title="Out-of-date embeddings">
            Stale: {{ counts.stale }}
          </span>
          <span class="emb-badge emb-missing" title="Missing embeddings">
            Missing: {{ counts.missing }}
          </span>

           <button
            class="btn btn-sm btn-primary btn-refresh-emb"
            :disabled="store.isEmbeddingRefreshing"
            @click="store.refreshEmbeddingsStream"
          >
            {{ store.isEmbeddingRefreshing ? 'Refreshing Embeddings...' : '⚡ Refresh Stale Embeddings' }}
          </button>
          
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../styles/variables' as *;

.selection-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 20px;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  font-size: 13px;
  position: relative;
  z-index: 100;
  min-height: 44px;
}

.selection-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.selection-right {
  display: flex;
  align-items: center;
}

.select-all-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  color: $color-text-secondary;

  input {
    accent-color: $color-primary;
  }
}

.batch-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}

.autogen-controls {
  display: flex;
  align-items: center;
  gap: 14px;
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
  padding: 5px 12px;
  cursor: pointer;

  &:hover {
    background-color: $color-primary-hover;
  }
}

.sse-progress-panel {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sse-indicator {
  display: flex;
  align-items: center;
  gap: 6px;

  .pulse-dot {
    width: 8px;
    height: 8px;
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
  width: 120px;
  height: 8px;
  background-color: rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: $color-primary;
  transition: width 0.2s ease;
}

.progress-numbers {
  font-size: 11px;
  font-family: $font-family-mono;
  color: $color-text-secondary;
}

.btn-cancel {
  font-size: 11px;
  padding: 3px 8px;
  background-color: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
  cursor: pointer;

  &:hover {
    background-color: rgba(239, 68, 68, 0.3);
  }
}

.embedding-bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn-refresh-emb {
  font-weight: 600;
}

.budget-popup-anchor {
  position: relative;
}

.btn-selected-range {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background-color: rgba(0, 0, 0, 0.04);
  border: 1px solid $color-border;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  color: $color-text-primary;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    border-color: $color-primary;
    background-color: rgba(232, 166, 67, 0.08);
  }

  .range-chevron {
    font-size: 9px;
    color: $color-text-muted;
  }
}

.budget-popup-card {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 270px;
  background-color: $color-surface;
  border: 1px solid $color-border;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.18), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 500;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 6px;
}

.popup-title {
  font-size: 12px;
  font-weight: 700;
  color: $color-text-primary;
}

.btn-close-popup {
  font-size: 12px;
  color: $color-text-muted;
  cursor: pointer;
  padding: 0 4px;

  &:hover {
    color: $color-text-primary;
  }
}

.popup-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: $color-text-muted;
}

.preset-buttons {
  display: flex;
  gap: 6px;
}

.btn-preset {
  flex: 1;
  background-color: rgba(0, 0, 0, 0.03);
  color: $color-text-secondary;
  border: 1px solid $color-border;
  padding: 4px 6px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: center;

  &:hover {
    color: $color-text-primary;
    border-color: $color-primary;
  }

  &.active {
    background-color: rgba(232, 166, 67, 0.18);
    border-color: $color-primary;
    color: #b87518;
    font-weight: 700;
  }
}

.custom-token-inputs {
  display: flex;
  align-items: center;
  gap: 12px;

  label {
    display: flex;
    align-items: center;
    gap: 6px;
    color: $color-text-secondary;
    font-size: 11.5px;
  }

  input {
    width: 64px;
    background-color: rgba(0, 0, 0, 0.04);
    border: 1px solid $color-border;
    padding: 3px 6px;
    color: $color-text-primary;
    font-size: 11.5px;
    outline: none;

    &:focus {
      border-color: $color-primary;
    }
  }
}

.proposals-toolbar-group {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: rgba(56, 189, 248, 0.1);
  padding: 4px 12px;
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.proposals-indicator {
  font-size: 12px;
  font-weight: 600;
  color: $color-primary;
}

.stat-pill {
  font-size: 11px;
  font-family: $font-family-mono;
  color: $color-text-muted;
  background-color: rgba(0, 0, 0, 0.05);
  padding: 4px 10px;
}

.embedding-status-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.emb-badge {
  font-size: 11px;
  font-family: $font-family-mono;
  font-weight: 600;
  padding: 3px 8px;

  &.emb-current {
    background-color: rgba(22, 163, 74, 0.12);
    color: $color-status-current;
    border: 1px solid rgba(22, 163, 74, 0.3);
  }

  &.emb-stale {
    background-color: rgba(234, 179, 8, 0.12);
    color: $color-status-stale;
    border: 1px solid rgba(234, 179, 8, 0.3);
  }

  &.emb-missing {
    background-color: rgba(239, 68, 68, 0.12);
    color: $color-status-missing;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
}

.btn {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;

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
    &:hover {
      background-color: lighten(#334155, 5%);
    }
  }

  &.btn-success {
    background-color: #22c55e;
    color: #000;
    font-weight: 600;
    &:hover {
      background-color: #16a34a;
    }
  }
}
</style>