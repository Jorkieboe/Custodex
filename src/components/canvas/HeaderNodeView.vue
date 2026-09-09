<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { type NodeItem } from '../../services/api'
import { useWorkspaceStore } from '../../stores/workspace'

const props = defineProps<{
  node: NodeItem
  childCount: number
}>()

const emit = defineEmits<{
  (e: 'demote', nodeId: string): void
}>()

const store = useWorkspaceStore()
const headerEditableRef = ref<HTMLDivElement | null>(null)
let saveTimeout: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  if (headerEditableRef.value) {
    headerEditableRef.value.innerText = props.node.text_content
  }
})

watch(
  () => props.node.text_content,
  (newVal) => {
    if (headerEditableRef.value && document.activeElement !== headerEditableRef.value) {
      headerEditableRef.value.innerText = newVal
    }
  }
)

function handleInput(event: Event) {
  const el = event.target as HTMLDivElement
  const val = el.innerText.trim()
  if (saveTimeout) clearTimeout(saveTimeout)
  saveTimeout = setTimeout(() => {
    if (val) {
      store.updateNode(props.node.id, val)
    }
  }, 400)
}

function handleBlur() {
  if (saveTimeout) clearTimeout(saveTimeout)
  if (headerEditableRef.value) {
    const val = headerEditableRef.value.innerText.trim()
    if (val && val !== props.node.text_content) {
      store.updateNode(props.node.id, val)
    }
  }
}
</script>

<template>
  <div class="header-node-container">
    <div class="header-bar">
      <div class="header-left">
        <span class="heading-tag">HEADER</span>
        <div
          ref="headerEditableRef"
          class="header-text-editable"
          contenteditable="true"
          spellcheck="false"
          @input="handleInput"
          @blur="handleBlur"
        ></div>
      </div>
      <div class="header-right">
        <span class="child-badge" :title="`${childCount} chunks attached under this header`">
          {{ childCount }} {{ childCount === 1 ? 'chunk' : 'chunks' }}
        </span>
        <button
         v-if="store.currentStep == 'chunks'"
          class="demote-btn"
          @click="emit('demote', node.id)"
          title="Demote header to paragraph chunk"
        >
          Demote to Chunk
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.header-node-container {
  margin: 18px 0 8px 0;
}

.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: rgba(56, 189, 248, 0.08);
  border-left: 4px solid $color-primary;
  border-radius: $radius-sm;
  padding: 8px 14px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.heading-tag {
  font-size: 10px;
  font-weight: 800;
  color: $color-primary;
  letter-spacing: 0.06em;
  background-color: rgba(56, 189, 248, 0.15);
  padding: 2px 6px;
  border-radius: $radius-sm;
  user-select: none;
}

.header-text-editable {
  font-size: 15px;
  font-weight: 700;
  color: $color-text-primary;
  outline: none;
  cursor: text;
  flex: 1;
  padding: 2px 4px;
  border-radius: $radius-sm;

  &:focus {
    background-color: rgba(255, 255, 255, 0.05);
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  user-select: none;
}

.child-badge {
  font-size: 11px;
  font-weight: 600;
  color: $color-text-secondary;
  background-color: rgba(255, 255, 255, 0.06);
  padding: 2px 8px;
  border-radius: 999px;
}

.demote-btn {
  font-size: 11px;
  color: $color-text-secondary;
  background-color: $color-surface-hover;
  border: 1px solid $color-border;
  padding: 3px 8px;
  border-radius: $radius-sm;
  cursor: pointer;

  &:hover {
    color: $color-text-primary;
    border-color: $color-primary;
  }
}
</style>