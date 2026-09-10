<script setup lang="ts">
import { ref, watch } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'

const store = useWorkspaceStore()
const localValues = ref<Record<string, any>>({})
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => store.activeNodeMetadata,
  (items) => {
    const vals: Record<string, any> = {}
    for (const item of items) {
      if (item.field_type === 'array[string]' && Array.isArray(item.field_value)) {
        vals[item.field_id] = item.field_value.join(', ')
      } else {
        vals[item.field_id] = item.field_value
      }
    }
    localValues.value = vals
  },
  { immediate: true, deep: true }
)

function handleValueChange(fieldId: string, rawVal: any, fieldType: string) {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    let finalVal = rawVal
    if (fieldType === 'number') {
      finalVal = rawVal === '' || rawVal === null ? null : Number(rawVal)
    } else if (fieldType === 'boolean') {
      finalVal = Boolean(rawVal)
    } else if (fieldType === 'array[string]') {
      finalVal = typeof rawVal === 'string' ? rawVal.split(',').map((s) => s.trim()).filter(Boolean) : rawVal
    }

    if (store.activeNodeId) {
      await store.saveNodeMetadataField(store.activeNodeId, fieldId, finalVal)
    }
  }, 350)
}
</script>

<template>
  <aside v-if="store.isInspectorOpen" class="metadata-inspector-drawer">
    <div class="drawer-header">
      <div>
        <h3>Chunk Metadata</h3>
        <span class="chunk-uuid" v-if="store.activeNodeId">
          ID: {{ store.activeNodeId.slice(0, 8) }}
        </span>
      </div>
      <button class="btn-close" @click="store.closeInspector" title="Close Inspector">✕</button>
    </div>

    <div v-if="!store.activeNodeId" class="empty-selection">
      Select a chunk to inspect or edit its metadata.
    </div>

    <div v-else-if="store.activeNodeMetadata.length === 0" class="empty-selection">
      No schema fields configured. Add fields in the Schema Designer first.
    </div>

    <div v-else class="metadata-fields-list">
      <div
        v-for="item in store.activeNodeMetadata"
        :key="item.field_id"
        class="meta-field-card"
      >
        <div class="meta-field-header">
          <div class="label-group">
            <span class="field-label">{{ item.field_label }}</span>
            <span v-if="item.is_required" class="required-star">*</span>
          </div>

          <div class="badges-group">
            <span
              v-if="item.user_edited"
              class="badge badge-human"
              title="Protected from LLM overwrite"
            >
              ✍️ Human Edited
            </span>
            <span v-else-if="item.field_value !== null" class="badge badge-ai">
              🤖 AI Generated
            </span>
            <span class="type-pill">{{ item.field_type }}</span>
          </div>
        </div>

        <p v-if="item.description" class="meta-field-desc">{{ item.description }}</p>

        <!-- Input based on field type -->
        <div class="input-container">
          <input
            v-if="item.field_type === 'string'"
            v-model="localValues[item.field_id]"
            type="text"
            class="input-control"
            placeholder="Enter value..."
            @input="handleValueChange(item.field_id, localValues[item.field_id], item.field_type)"
          />

          <input
            v-else-if="item.field_type === 'number'"
            v-model="localValues[item.field_id]"
            type="number"
            class="input-control"
            placeholder="0"
            @input="handleValueChange(item.field_id, localValues[item.field_id], item.field_type)"
          />

          <label v-else-if="item.field_type === 'boolean'" class="switch-container">
            <input
              type="checkbox"
              v-model="localValues[item.field_id]"
              @change="handleValueChange(item.field_id, localValues[item.field_id], item.field_type)"
            />
            <span class="switch-label">{{ localValues[item.field_id] ? 'True' : 'False' }}</span>
          </label>

          <input
            v-else-if="item.field_type === 'date'"
            v-model="localValues[item.field_id]"
            type="date"
            class="input-control"
            @change="handleValueChange(item.field_id, localValues[item.field_id], item.field_type)"
          />

          <input
            v-else-if="item.field_type === 'array[string]'"
            v-model="localValues[item.field_id]"
            type="text"
            class="input-control"
            placeholder="Comma-separated tags (tag1, tag2)..."
            @input="handleValueChange(item.field_id, localValues[item.field_id], item.field_type)"
          />

          <input
            v-else
            v-model="localValues[item.field_id]"
            type="text"
            class="input-control"
            @input="handleValueChange(item.field_id, localValues[item.field_id], item.field_type)"
          />
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.metadata-inspector-drawer {
  width: 360px;
  background-color: $color-surface;
  border-left: 1px solid $color-border;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.drawer-header {
  padding: 16px;
  border-bottom: 1px solid $color-border;
  display: flex;
  justify-content: space-between;
  align-items: center;

  h3 {
    font-size: 15px;
    font-weight: 700;
  }

  .chunk-uuid {
    font-family: $font-family-mono;
    font-size: 11px;
    color: $color-text-muted;
  }

  .btn-close {
    background: transparent;
    color: $color-text-muted;
    font-size: 16px;
    &:hover { color: $color-text-primary; }
  }
}

.empty-selection {
  padding: 32px 16px;
  text-align: center;
  color: $color-text-muted;
  font-size: 13px;
}

.metadata-fields-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.meta-field-card {
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid $color-border;
  border-radius: $radius-sm;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-field-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.label-group {
  display: flex;
  align-items: center;
  gap: 4px;

  .field-label {
    font-size: 12px;
    font-weight: 600;
    color: $color-text-primary;
  }

  .required-star {
    color: $color-status-missing;
    font-size: 12px;
  }
}

.badges-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: $radius-sm;
  font-weight: 500;

  &.badge-human {
    background-color: rgba(56, 189, 248, 0.15);
    color: $color-primary;
  }

  &.badge-ai {
    background-color: rgba(74, 222, 128, 0.15);
    color: $color-status-current;
  }
}

.type-pill {
  font-size: 10px;
  color: $color-text-muted;
  background-color: rgba(255, 255, 255, 0.05);
  padding: 2px 5px;
  border-radius: $radius-sm;
}

.meta-field-desc {
  font-size: 11px;
  color: $color-text-muted;
  line-height: 1.3;
}

.input-container {
  display: flex;
}

.input-control {
  width: 100%;
  background-color: rgba(0, 0, 0, 0.3);
  border: 1px solid $color-border;
  border-radius: $radius-sm;
  padding: 6px 10px;
  font-size: 12px;
  color: $color-text-primary;
  outline: none;

  &:focus {
    border-color: $color-primary;
  }
}

.switch-container {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  cursor: pointer;
}
</style>