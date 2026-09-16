<script setup lang="ts">
import { ref, computed } from 'vue'
import { type NodeItem } from '../../services/api'
import { useWorkspaceStore } from '../../stores/workspace'
import HeaderNodeView from './HeaderNodeView.vue'
import ChunkNodeView from './ChunkNodeView.vue'

const store = useWorkspaceStore()

const isAutoSplitting = ref(false)
const floatingToolbarVisible = ref(false)

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
const floatingToolbarPos = ref({ x: 0, y: 0 })
const activeSelection = ref<{
  nodeId: string
  text: string
  start: number
  end: number
} | null>(null)

const headerChildCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const node of store.nodes) {
    if (node.node_type === 'paragraph' && node.parent_id) {
      counts[node.parent_id] = (counts[node.parent_id] || 0) + 1
    }
  }
  return counts
})

function handleSelectionChange(nodeId: string, text: string, start: number, end: number) {
  activeSelection.value = { nodeId, text, start, end }
  const selection = window.getSelection()
  if (selection && selection.rangeCount > 0) {
    const rect = selection.getRangeAt(0).getBoundingClientRect()
    floatingToolbarPos.value = {
      x: rect.left + rect.width / 2,
      y: rect.top - 40
    }
    floatingToolbarVisible.value = true
  }
}

function clearSelection() {
  floatingToolbarVisible.value = false
  activeSelection.value = null
}

async function handleMakeHeader() {
  if (!activeSelection.value) return
  const { nodeId, start, end } = activeSelection.value
  await store.detachSelection(nodeId, start, end)
  clearSelection()
}

async function handleSplitFromSelection() {
  if (!activeSelection.value) return
  const { nodeId, start } = activeSelection.value
  const targetNode = store.nodes.find((n: NodeItem) => n.id === nodeId)
  if (!targetNode) return
  const top = targetNode.text_content.slice(0, start).trim()
  const bottom = targetNode.text_content.slice(start).trim()
  if (top && bottom) {
    await store.splitNode(nodeId, top, bottom)
  }
  clearSelection()
}

function canMerge(index: number): boolean {
  if (index >= store.nodes.length - 1) return false
  const current = store.nodes[index]
  const next = store.nodes[index + 1]
  return current.node_type === 'paragraph' && next.node_type === 'paragraph'
}
</script>

<template>
  <div class="chunk-canvas-wrapper" @click="clearSelection">
    <!-- Autosplit Token Range Configuration Bar -->
    <div v-if="store.nodes.length > 0 && store.currentStep == 'chunks'" class="autosplit-config-bar">
      <div class="config-title">
        <span class="bolt-icon">⚡</span>
        <span>Chunk Token Budget:</span>
      </div>

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

    <!-- Multi-Chunk Selection Toolbar -->
    <div v-if="store.nodes.length > 0" class="selection-action-bar">
      <div class="selection-info">
        <label class="select-all-label">
          <input
            type="checkbox"
            :checked="store.selectedNodeIds.size === store.nodes.length && store.nodes.length > 0"
            @change="$event => ($event.target as HTMLInputElement).checked ? store.selectAllNodes() : store.clearNodeSelection()"
          />
          <span>Select All ({{ store.selectedNodeIds.size }} / {{ store.nodes.length }})</span>
        </label>
      </div>

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
    </div>

    <!-- Visual Canvas Content -->
    <div class="canvas-scroll-container">
      <div v-if="store.documents.length === 0" class="canvas-empty">
        <p>No documents imported yet. Import documents from Ingestion to get started.</p>
      </div>

      <div v-else-if="store.nodes.length === 0" class="canvas-empty">
        <p>Document has no structural nodes.</p>
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
            @selection-change="handleSelectionChange"
          />
        </template>
      </div>
    </div>

    <!-- Floating Text Selection Toolbar -->
    <div
      v-if="floatingToolbarVisible"
      class="floating-selection-toolbar"
      :style="{ top: `${floatingToolbarPos.y}px`, left: `${floatingToolbarPos.x}px` }"
      @click.stop
    >
      <button class="float-btn" @click="handleMakeHeader">
        ✦ Make Header
      </button>
      <button class="float-btn" @click="handleSplitFromSelection">
        ✂ Split Chunk Here
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.chunk-canvas-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: calc(100vh - #{$header-height});
  background-color: $color-bg;
  position: relative;
}

.autosplit-config-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 24px;
  background-color: rgba(0, 0, 0, 0.25);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 12px;
}

.config-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: $color-text-secondary;

  .bolt-icon {
    color: $color-primary;
  }
}

.preset-buttons {
  display: flex;
  gap: 6px;
}

.btn-preset {
  background-color: $color-surface;
  color: $color-text-secondary;
  border: 1px solid $color-border;
  border-radius: $radius-sm;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    color: $color-text-primary;
    border-color: $color-primary;
  }

  &.active {
    background-color: rgba(56, 189, 248, 0.15);
    border-color: $color-primary;
    color: $color-primary;
    font-weight: 700;
  }
}

.custom-token-inputs {
  display: flex;
  align-items: center;
  gap: 8px;

  label {
    display: flex;
    align-items: center;
    gap: 4px;
    color: $color-text-muted;
    font-size: 11px;
  }

  input {
    width: 58px;
    background-color: rgba(0, 0, 0, 0.3);
    border: 1px solid $color-border;
    border-radius: $radius-sm;
    padding: 2px 6px;
    color: $color-text-primary;
    font-size: 11px;
    outline: none;

    &:focus {
      border-color: $color-primary;
    }
  }
}

.selection-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 24px;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  font-size: 13px;
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
  gap: 12px;
}

.batch-hint {
  font-size: 12px;
  color: $color-text-muted;
}

.canvas-scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.nodes-list {
  max-width: 860px;
  margin: 0 auto;
}

.canvas-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: $color-text-muted;
  font-size: 15px;
}

.floating-selection-toolbar {
  position: fixed;
  transform: translateX(-50%);
  background-color: $color-surface;
  border: 1px solid $color-primary;
  border-radius: $radius-md;
  box-shadow: $shadow-modal;
  display: flex;
  padding: 4px;
  gap: 4px;
  z-index: 3000;
}

.float-btn {
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  color: $color-text-primary;
  border-radius: $radius-sm;
  cursor: pointer;

  &:hover {
    background-color: $color-primary;
    color: #000;
  }
}

.btn {
  padding: 4px 10px;
  border-radius: $radius-md;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;

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

.proposals-toolbar-group {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: rgba(56, 189, 248, 0.1);
  padding: 4px 12px;
  border-radius: $radius-sm;
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.proposals-indicator {
  font-size: 12px;
  font-weight: 600;
  color: $color-primary;
}
</style>