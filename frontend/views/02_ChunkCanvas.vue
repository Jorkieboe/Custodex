<script setup lang="ts">
import { ref, computed } from 'vue'
import { type NodeItem } from '../services/api.ts'
import { useWorkspaceStore } from '../stores/workspace.ts'
import HeaderNodeView from '../components/canvas/HeaderNodeView.vue'
import ChunkNodeView from '../components/canvas/ChunkNodeView.vue'
import HeaderOutlineLegend from '../components/canvas/HeaderOutlineLegend.vue'
import ActionBar from '../components/ActionBar.vue'

const store = useWorkspaceStore()

const floatingToolbarVisible = ref(false)
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

function handleWrapperClick() {
  clearSelection()
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
  <div class="chunk-canvas-wrapper" @click="handleWrapperClick">
    <!-- Context-Aware Selection Action Bar -->
    <ActionBar />

    <!-- Visual Canvas Content with Side Legend: 20% headeroutline, 60% chunks, 20% empty panel -->
    <div class="canvas-main-area">
      <HeaderOutlineLegend />
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
      <div class="canvas-empty-panel"></div>
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
@use '../styles/variables' as *;

.chunk-canvas-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: calc(100vh - #{$header-height});
  background-color: $color-bg;
  position: relative;
}

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

.budget-popup-anchor {
  position: relative;
}

.btn-selected-range {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background-color: rgba(0, 0, 0, 0.04);
  border: 1px solid $color-border;
  border-radius: $radius-md;
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
  border-radius: $radius-md;
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
  border-radius: $radius-sm;
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
    border-radius: $radius-sm;
    padding: 3px 6px;
    color: $color-text-primary;
    font-size: 11.5px;
    outline: none;

    &:focus {
      border-color: $color-primary;
    }
  }
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

.canvas-main-area {
  display: grid;
  grid-template-columns: 20% 60% 20%;
  flex: 1;
  overflow: hidden;
  position: relative;

  > :first-child {
    min-width: 0;
    overflow-y: auto;
  }
}

.canvas-scroll-container {
  min-width: 0;
  overflow-y: auto;
  padding: 24px;
}

.canvas-empty-panel {
  min-width: 0;
  border-left: 1px solid $color-border;
  background-color: transparent;
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