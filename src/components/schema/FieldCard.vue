<script setup lang="ts">
import { ref, watch } from 'vue'
import { type SchemaField } from '../../services/api'

const props = defineProps<{
  field: SchemaField
  isFirst: boolean
  isLast: boolean
}>()

const emit = defineEmits<{
  (e: 'update', fieldId: string, data: Partial<SchemaField>): void
  (e: 'delete', fieldId: string): void
  (e: 'move-up', fieldId: string): void
  (e: 'move-down', fieldId: string): void
}>()

const label = ref(props.field.field_label)
const slug = ref(props.field.field_slug)
const fieldType = ref(props.field.field_type)
const description = ref(props.field.description)
const isRequired = ref(props.field.is_required)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function triggerSave() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('update', props.field.id, {
      field_label: label.value,
      field_slug: slug.value,
      field_type: fieldType.value,
      description: description.value,
      is_required: isRequired.value
    })
  }, 350)
}

function handleLabelInput() {
  // If slug matches former slugified label, keep it in sync
  triggerSave()
}

watch(
  () => props.field,
  (newVal) => {
    label.value = newVal.field_label
    slug.value = newVal.field_slug
    fieldType.value = newVal.field_type
    description.value = newVal.description
    isRequired.value = newVal.is_required
  },
  { deep: true }
)

const typeIcons: Record<string, string> = {
  string: '🔤',
  number: '🔢',
  boolean: '🔘',
  'array[string]': '🏷️',
  'array[number]': '📊',
  date: '📅'
}
</script>

<template>
  <div class="field-card">
    <div class="field-card-header">
      <div class="field-type-pill">
        <span class="type-icon">{{ typeIcons[fieldType] || '📄' }}</span>
        <select v-model="fieldType" class="type-select" @change="triggerSave">
          <option value="string">Text (string)</option>
          <option value="number">Number (number)</option>
          <option value="boolean">Boolean (true/false)</option>
          <option value="array[string]">Tag List (array[string])</option>
          <option value="array[number]">Number Array (array[number])</option>
          <option value="date">Date (ISO-8601)</option>
        </select>
      </div>

      <div class="field-uuid-badge" :title="`Field UUID: ${field.id}`">
        ID: {{ field.id.slice(0, 8) }}
      </div>

      <div class="field-actions">
        <button
          class="btn-icon"
          :disabled="isFirst"
          @click="emit('move-up', field.id)"
          title="Move field up"
        >
          ▲
        </button>
        <button
          class="btn-icon"
          :disabled="isLast"
          @click="emit('move-down', field.id)"
          title="Move field down"
        >
          ▼
        </button>
        <button
          class="btn-icon btn-delete"
          @click="emit('delete', field.id)"
          title="Delete field"
        >
          ✕
        </button>
      </div>
    </div>

    <div class="field-card-body">
      <div class="field-row">
        <div class="input-group flex-2">
          <label>Field Display Label</label>
          <input
            v-model="label"
            type="text"
            placeholder="e.g. Primary Topic"
            @input="handleLabelInput"
          />
        </div>

        <div class="input-group flex-2">
          <label>Schema Key / Slug</label>
          <input
            v-model="slug"
            type="text"
            placeholder="primary_topic"
            @input="triggerSave"
          />
        </div>

        <div class="input-group flex-1 toggle-group">
          <label>Required</label>
          <label class="switch">
            <input
              type="checkbox"
              v-model="isRequired"
              @change="triggerSave"
            />
            <span class="slider"></span>
          </label>
        </div>
      </div>

      <div class="field-row">
        <div class="input-group flex-1">
          <label>Field description</label>
          <textarea
            v-model="description"
            rows="2"
            placeholder="Instructions guiding how the LLM extracts or classifies this field..."
            @input="triggerSave"
          ></textarea>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.field-card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  transition: border-color 0.15s ease;

  &:hover {
    border-color: rgba(56, 189, 248, 0.4);
  }
}

.field-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background-color: rgba(0, 0, 0, 0.15);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.field-type-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  background-color: rgba(56, 189, 248, 0.1);
  padding: 2px 8px;
  border-radius: $radius-sm;
  font-size: 11px;
}

.type-select {
  background: transparent;
  color: $color-primary;
  border: none;
  font-size: 12px;
  font-weight: 600;
  outline: none;
  cursor: pointer;

  option {
    background-color: $color-surface;
    color: $color-text-primary;
  }
}

.field-uuid-badge {
  font-family: $font-family-mono;
  font-size: 10px;
  color: $color-text-muted;
  background-color: rgba(255, 255, 255, 0.04);
  padding: 2px 6px;
  border-radius: $radius-sm;
}

.field-actions {
  display: flex;
  gap: 4px;
}

.btn-icon {
  background: transparent;
  color: $color-text-secondary;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: $radius-sm;

  &:hover:not(:disabled) {
    background-color: $color-surface-hover;
    color: $color-text-primary;
  }

  &:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  &.btn-delete:hover {
    color: $color-status-missing;
    background-color: $color-status-missing-bg;
  }
}

.field-card-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-row {
  display: flex;
  gap: 12px;
}

.flex-1 { flex: 1; }
.flex-2 { flex: 2; }

.input-group {
  display: flex;
  flex-direction: column;
  gap: 4px;

  label {
    font-size: 11px;
    font-weight: 600;
    color: $color-text-secondary;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  input, textarea {
    background-color: rgba(0, 0, 0, 0.25);
    border: 1px solid $color-border;
    border-radius: $radius-sm;
    padding: 6px 10px;
    font-size: 13px;
    color: $color-text-primary;
    outline: none;

    &:focus {
      border-color: $color-primary;
    }
  }

  textarea {
    resize: vertical;
    line-height: 1.4;
  }
}

.toggle-group {
  align-items: center;
  justify-content: center;
}

.switch {
  position: relative;
  display: inline-block;
  width: 38px;
  height: 20px;

  input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .slider {
    position: absolute;
    cursor: pointer;
    inset: 0;
    background-color: rgba(255, 255, 255, 0.1);
    transition: 0.2s;
    border-radius: 20px;

    &::before {
      position: absolute;
      content: "";
      height: 14px;
      width: 14px;
      left: 3px;
      bottom: 3px;
      background-color: white;
      transition: 0.2s;
      border-radius: 50%;
    }
  }

  input:checked + .slider {
    background-color: $color-primary;
  }

  input:checked + .slider::before {
    transform: translateX(18px);
    background-color: #000;
  }
}
</style>