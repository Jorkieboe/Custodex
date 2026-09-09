<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { type NodeItem } from '../../services/api'
import { useWorkspaceStore } from '../../stores/workspace'

const props = defineProps<{
  node: NodeItem
  canMerge: boolean
}>()

const emit = defineEmits<{
  (e: 'split', nodeId: string, topText: string, bottomText: string): void
  (e: 'merge', nodeId: string): void
  (e: 'promote', nodeId: string): void
  (e: 'selection-change', nodeId: string, text: string, start: number, end: number): void
}>()

const store = useWorkspaceStore()
const chunkRef = ref<HTMLDivElement | null>(null)
const segmentRefs = ref<HTMLDivElement[]>([])
const segments = ref<string[]>([])
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const contextSegmentIndex = ref<number | null>(null)
const contextCaretOffset = ref<number | null>(null)
let saveTimeout: ReturnType<typeof setTimeout> | null = null

// Step-aware rule: indicator is exclusively visible during the 'embeddings' step
const showEmbeddingStatus = computed(() => store.currentStep === 'embeddings')
const isSelected = computed(() => store.selectedNodeIds.has(props.node.id))

function parseSegmentsFromText(rawText: string): string[] {
  const parts = rawText.split(/\n\s*\n/)
  return parts.length > 0 ? parts : ['']
}

function initSegments(text: string) {
  segments.value = parseSegmentsFromText(text)
  nextTick(() => {
    segmentRefs.value.forEach((el, idx) => {
      if (el && segments.value[idx] !== undefined) {
        el.innerText = segments.value[idx]
      }
    })
  })
}

onMounted(() => {
  initSegments(props.node.text_content)
})

watch(
  () => props.node.text_content,
  (newVal) => {
    const isEditing = segmentRefs.value.some((el) => el === document.activeElement)
    if (!isEditing) {
      initSegments(newVal)
    }
  }
)

const contextMenuItems = computed(() => {
  const items = []

  if (store.currentStep === 'chunks') {
    items.push(
      {
        label: '✂️ Split Chunk Here',
        action: handleContextSplit,
      },
      {
        label: '↥ Promote to Header',
        action: () => emit('promote', props.node.id),
      },
    )

    if (props.canMerge) {
      items.push({
        label: '⤓ Merge with Below',
        action: () => emit('merge', props.node.id),
      })
    }
  }

  if (store.currentStep === 'embeddings') {
    items.push({
        label: 'Generate Embeddings',
        action: () => {},
      })
  }

  return items
})

function setSegmentRef(el: any, idx: number) {
  if (el) {
    segmentRefs.value[idx] = el as HTMLDivElement
  }
}

function handleSegmentInput(idx: number, event: Event) {
  const el = event.target as HTMLDivElement
  const currentVal = el.innerText

  // Check if double enter was typed or pasted inside this div
  if (currentVal.includes('\n\n')) {
    const innerParts = currentVal.split(/\n\s*\n/)
    segments.value.splice(idx, 1, ...innerParts)
    persistFullText()

    nextTick(() => {
      segmentRefs.value.forEach((targetEl, i) => {
        if (targetEl && segments.value[i] !== undefined) {
          targetEl.innerText = segments.value[i]
        }
      })
      // Focus into the subsequent segment
      const nextEl = segmentRefs.value[idx + 1]
      if (nextEl) {
        nextEl.focus()
      }
    })
    return
  }

  segments.value[idx] = currentVal
  persistFullText()
}

function handleSegmentKeyDown(idx: number, event: KeyboardEvent) {
  const el = segmentRefs.value[idx]
  if (!el) return

  // Detect double enter: Enter pressed when cursor is at the end of an empty line
  if (event.key === 'Enter' && !event.shiftKey) {
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0)
      const preRange = range.cloneRange()
      preRange.selectNodeContents(el)
      preRange.setEnd(range.endContainer, range.endOffset)
      const textBefore = preRange.toString()

      if (textBefore.endsWith('\n')) {
        event.preventDefault()
        const topText = textBefore.replace(/\n$/, '').trim()
        const full = el.innerText
        const bottomText = full.slice(textBefore.length).trim()

        segments.value[idx] = topText
        segments.value.splice(idx + 1, 0, bottomText)
        persistFullText()

        nextTick(() => {
          segmentRefs.value.forEach((targetEl, i) => {
            if (targetEl && segments.value[i] !== undefined) {
              targetEl.innerText = segments.value[i]
            }
          })
          const nextEl = segmentRefs.value[idx + 1]
          if (nextEl) {
            nextEl.focus()
          }
        })
        return
      }
    }
  }

  // Backspace at the beginning of a segment: merge with previous segment
  if (event.key === 'Backspace' && idx > 0) {
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0 && selection.isCollapsed) {
      const range = selection.getRangeAt(0)
      const preRange = range.cloneRange()
      preRange.selectNodeContents(el)
      preRange.setEnd(range.endContainer, range.endOffset)
      if (preRange.toString().length === 0) {
        event.preventDefault()
        const prevText = segments.value[idx - 1]
        const currText = segments.value[idx]
        const mergedText = prevText + (currText ? '\n' + currText : '')

        segments.value[idx - 1] = mergedText
        segments.value.splice(idx, 1)
        segmentRefs.value.splice(idx, 1)
        persistFullText()

        nextTick(() => {
          segmentRefs.value.forEach((targetEl, i) => {
            if (targetEl && segments.value[i] !== undefined) {
              targetEl.innerText = segments.value[i]
            }
          })
          const prevEl = segmentRefs.value[idx - 1]
          if (prevEl) {
            prevEl.focus()
          }
        })
      }
    }
  }
}

function persistFullText() {
  const full = segments.value.join('\n\n')
  if (saveTimeout) clearTimeout(saveTimeout)
  saveTimeout = setTimeout(() => {
    store.updateNode(props.node.id, full)
  }, 400)
}

function handleSegmentBlur() {
  if (saveTimeout) clearTimeout(saveTimeout)
  const full = segments.value.join('\n\n')
  if (full !== props.node.text_content) {
    store.updateNode(props.node.id, full)
  }
}

function handleSplitBetween(dividerIndex: number) {
  const topText = segments.value.slice(0, dividerIndex + 1).join('\n\n').trim()
  const bottomText = segments.value.slice(dividerIndex + 1).join('\n\n').trim()
  if (topText && bottomText) {
    emit('split', props.node.id, topText, bottomText)
  }
}

function handleContextMenu(event: MouseEvent) {
  event.preventDefault()
  contextMenuPosition.value = { x: event.clientX, y: event.clientY }
  contextMenuVisible.value = true

  const selection = window.getSelection()
  contextSegmentIndex.value = null
  contextCaretOffset.value = null

  if (selection && selection.focusNode) {
    const foundIdx = segmentRefs.value.findIndex((el) => el && el.contains(selection.focusNode))
    if (foundIdx !== -1) {
      contextSegmentIndex.value = foundIdx
      const range = selection.getRangeAt(0)
      const preRange = range.cloneRange()
      preRange.selectNodeContents(segmentRefs.value[foundIdx])
      preRange.setEnd(range.endContainer, range.endOffset)
      contextCaretOffset.value = preRange.toString().length
    }
  }
}

function closeContextMenu() {
  contextMenuVisible.value = false
}

function handleContextSplit() {
  if (contextSegmentIndex.value !== null && contextCaretOffset.value !== null) {
    const idx = contextSegmentIndex.value
    const offset = contextCaretOffset.value
    const segText = segments.value[idx] || ''

    const segTop = segText.slice(0, offset).trim()
    const segBottom = segText.slice(offset).trim()

    const topParts = [...segments.value.slice(0, idx), segTop].filter(Boolean)
    const bottomParts = [segBottom, ...segments.value.slice(idx + 1)].filter(Boolean)

    const top = topParts.join('\n\n').trim()
    const bottom = bottomParts.join('\n\n').trim()

    if (top && bottom) {
      emit('split', props.node.id, top, bottom)
    }
  } else if (segments.value.length > 1) {
    handleSplitBetween(0)
  }
  closeContextMenu()
}

function handleSegmentMouseUp(idx: number, event: MouseEvent) {
  const selection = window.getSelection()
  if (!selection || selection.isCollapsed) return
  const text = selection.toString().trim()
  const el = segmentRefs.value[idx]
  if (text.length > 0 && el && el.contains(selection.anchorNode)) {
    let precedingCharCount = 0
    for (let i = 0; i < idx; i++) {
      precedingCharCount += segments.value[i].length + 2
    }
    const range = selection.getRangeAt(0)
    const preRange = range.cloneRange()
    preRange.selectNodeContents(el)
    preRange.setEnd(range.startContainer, range.startOffset)
    const startInSeg = preRange.toString().length
    const globalStart = precedingCharCount + startInSeg
    emit('selection-change', props.node.id, text, globalStart, globalStart + text.length)
  }
}
</script>

<template>
  <div
    ref="chunkRef"
    class="chunk-node-container"
    :class="{ selected: isSelected }"
    @contextmenu="handleContextMenu"
  >
    <div class="chunk-header">
      <div class="chunk-meta">
        <input
          type="checkbox"
          class="chunk-checkbox"
          :checked="isSelected"
          @change="store.toggleNodeSelection(node.id)"
        />
        <span class="order-badge">#{{ node.order_index }}</span>

        <!-- Embedding status indicator pill (step-aware: exclusively visible during embeddings step) -->
        <span
          v-if="showEmbeddingStatus"
          class="status-pill"
          :class="`status-${node.embedding_status}`"
        >
          <span class="status-dot"></span>
          {{ node.embedding_status.toUpperCase() }}
        </span>
      </div>

      <div class="chunk-tools" v-if="store.currentStep == 'chunks'">
        <button
          v-if="canMerge"
          class="btn-tool"
          @click="emit('merge', node.id)"
          title="Merge with succeeding chunk"
        >
          Merge Down ⤓
        </button>
        <button
          class="btn-tool"
          @click="emit('promote', node.id)"
          title="Promote paragraph to structural header"
        >
          Promote to Header ↥
        </button>
      </div>
    </div>

    <!-- Chunk Content Body: Each block of text in its own div, with split buttons strictly between them -->
    <div class="chunk-body">
      <template v-for="(seg, idx) in segments" :key="idx">
        <div
          :ref="el => setSegmentRef(el, idx)"
          class="chunk-editable-content"
          :contenteditable="store.currentStep == 'chunks'"
          spellcheck="false"
          @input="e => handleSegmentInput(idx, e)"
          @keydown="e => handleSegmentKeyDown(idx, e)"
          @blur="handleSegmentBlur"
          @mouseup="e => handleSegmentMouseUp(idx, e)"
        ></div>

        <!-- Interactive hover split divider positioned directly between separated text divs -->
        <div
          v-if="idx < segments.length - 1 && store.currentStep == 'chunks'"
          class="hover-split-divider"
          @click="handleSplitBetween(idx)"
          title="Click to split chunk here"
        >
          <div class="divider-line"></div>
          <button class="split-pill-btn" type="button">✂ Split Chunk Here</button>
        </div>
      </template>
    </div>

    <!-- Right-Click Context Menu -->
    <div
      v-if="contextMenuVisible && contextMenuItems.length > 0"
      class="context-menu-backdrop"
      @click="closeContextMenu"
    >
      <div
        class="context-menu"
        :style="{ top: `${contextMenuPosition.y}px`, left: `${contextMenuPosition.x}px` }"
        @click.stop
      >
        <button
          v-for="item in contextMenuItems"
          :key="item.label"
          class="context-item"
          @click="item.action"
        >
          {{ item.label }}
    </button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.chunk-node-container {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  margin-bottom: 12px;
  position: relative;
  transition: all 0.15s ease;

  &:hover {
    border-color: rgba(56, 189, 248, 0.4);
  }

  &.selected {
    border-color: $color-primary;
    background-color: rgba(56, 189, 248, 0.03);
  }
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  user-select: none;
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chunk-checkbox {
  cursor: pointer;
  accent-color: $color-primary;
}

.order-badge {
  font-family: $font-family-mono;
  font-size: 11px;
  color: $color-text-muted;
  background-color: rgba(0, 0, 0, 0.25);
  padding: 1px 6px;
  border-radius: $radius-sm;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  &.status-current {
    background-color: $color-status-current-bg;
    color: $color-status-current;
    .status-dot { background-color: $color-status-current; }
  }

  &.status-stale {
    background-color: $color-status-stale-bg;
    color: $color-status-stale;
    .status-dot { background-color: $color-status-stale; }
  }

  &.status-missing {
    background-color: $color-status-missing-bg;
    color: $color-status-missing;
    .status-dot { background-color: $color-status-missing; }
  }
}

.chunk-tools {
  display: flex;
  gap: 6px;
}

.btn-tool {
  font-size: 11px;
  color: $color-text-secondary;
  background-color: transparent;
  padding: 2px 6px;
  border-radius: $radius-sm;

  &:hover {
    color: $color-text-primary;
    background-color: $color-surface-hover;
  }
}

.chunk-body {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
}

.chunk-editable-content {
  font-size: 14px;
  line-height: 1.6;
  color: $color-text-primary;
  white-space: pre-wrap;
  outline: none;
  min-height: 24px;
  cursor: text;
  word-break: break-word;
  padding: 4px 6px;
  border-radius: $radius-sm;
  transition: background-color 0.15s ease;

  &:focus {
    background-color: rgba(255, 255, 255, 0.03);
  }
}

.hover-split-divider {
  position: relative;
  margin: 10px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  height: 24px;
  user-select: none;

  .divider-line {
    width: 100%;
    height: 1px;
    border-top: 1px dashed $color-border;
  }

  .split-pill-btn {
    position: absolute;
    background-color: $color-surface;
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: $color-primary;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 12px;
    border-radius: 999px;
    opacity: 0.5;
    transition: all 0.15s ease;
    cursor: pointer;
  }

  &:hover {
    .divider-line {
      border-top: 1px dashed $color-primary;
    }
    .split-pill-btn {
      opacity: 1;
      transform: scale(1.05);
      background-color: $color-primary;
      color: #000;
      border-color: $color-primary;
    }
  }
}

.context-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
}

.context-menu {
  position: fixed;
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  box-shadow: $shadow-modal;
  display: flex;
  flex-direction: column;
  padding: 4px;
  min-width: 160px;
  z-index: 2001;
}

.context-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: $color-text-primary;
  border-radius: $radius-sm;
  text-align: left;
  cursor: pointer;

  &:hover {
    background-color: $color-surface-hover;
    color: $color-primary;
  }
}
</style>