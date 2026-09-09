<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { type FieldType, type SchemaField } from '../../services/api'

const store = useWorkspaceStore()

const showAddFieldModal = ref(false)
const fieldLabel = ref('')
const fieldSlug = ref('')
const fieldType = ref<FieldType>('string')
const fieldDescription = ref('')
const fieldRequired = ref(false)

const supportedTypes: { type: FieldType; label: string; icon: string }[] = [
  { type: 'string', label: 'Short Text', icon: '📝' },
  { type: 'number', label: 'Number', icon: '🔢' },
  { type: 'boolean', label: 'Boolean Toggle', icon: '🔘' },
  { type: 'array[string]', label: 'Tag List (array[string])', icon: '🏷️' },
  { type: 'array[number]', label: 'Number List (array[number])', icon: '📊' },
  { type: 'date', label: 'ISO Date', icon: '📅' }
]

function handleLabelChange() {
  if (!fieldSlug.value || fieldSlug.value === slugify(fieldLabel.value.slice(0, -1))) {
    fieldSlug.value = slugify(fieldLabel.value)
  }
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

async function handleAddField() {
  if (!fieldLabel.value.trim() || !fieldSlug.value.trim()) return

  await store.addSchemaField({
    field_label: fieldLabel.value.trim(),
    field_slug: fieldSlug.value.trim(),
    field_type: fieldType.value,
    description: fieldDescription.value.trim(),
    is_required: fieldRequired.value
  })

  fieldLabel.value = ''
  fieldSlug.value = ''
  fieldType.value = 'string'
  fieldDescription.value = ''
  fieldRequired.value = false
  showAddFieldModal.value = false
}

async function handleDeleteField(fieldId: string) {
  await store.removeSchemaField(fieldId)
}

async function handleToggleRequired(field: SchemaField) {
  await store.modifySchemaField(field.id, { is_required: !field.is_required })
}
</script>

<template>
  <div class="schema-designer-wrapper">
    <div class="schema-header">
      <div>
        <h2>CMS Metadata Schema Designer</h2>
        <p class="subtitle">Architect extraction models with persistent UUID field anchors decoupled from field renames.</p>
      </div>
      <button class="btn btn-primary" @click="showAddFieldModal = true">
        + Add Field
      </button>
    </div>

    <div class="schema-body">
      <div v-if="store.schemaFields.length === 0" class="schema-empty-state">
        <span class="empty-icon">📐</span>
        <h3>No Schema Fields Defined</h3>
        <p>Define metadata attributes for your RAG dataset. Fields compile directly into JSON Schema validation rules.</p>
        <button class="btn btn-primary" @click="showAddFieldModal = true">
          Add First Field
        </button>
      </div>

      <div v-else class="fields-grid">
        <div
          v-for="field in store.schemaFields"
          :key="field.id"
          class="field-card"
        >
          <div class="field-card-top">
            <div class="field-identity">
              <span class="type-pill">{{ field.field_type }}</span>
              <h4 class="field-title">{{ field.field_label }}</h4>
            </div>
            <button
              class="btn-icon btn-danger"
              @click="handleDeleteField(field.id)"
              title="Delete field"
            >
              ✕
            </button>
          </div>

          <div class="field-slug-row">
            <span class="slug-tag">{{ field.field_slug }}</span>
            <label class="required-toggle">
              <input
                type="checkbox"
                :checked="field.is_required"
                @change="handleToggleRequired(field)"
              />
              <span>Required</span>
            </label>
          </div>

          <p class="field-desc">
            {{ field.description || 'No prompt instructions provided.' }}
          </p>

          <div class="field-footer">
            <span class="uuid-badge">{{ field.id.slice(0, 8) }}...</span>
            <span class="order-badge">Index: {{ field.order_index }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Field Modal -->
    <div v-if="showAddFieldModal" class="modal-backdrop" @click.self="showAddFieldModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Add Metadata Field</h3>
          <button class="close-btn" @click="showAddFieldModal = false">✕</button>
        </div>

        <div class="modal-body">
          <div class="form-group">
            <label>Field Display Label</label>
            <input
              v-model="fieldLabel"
              type="text"
              placeholder="e.g. Document Summary"
              autofocus
              @input="handleLabelChange"
            />
          </div>

          <div class="form-group">
            <label>Field Slug (JSON Key)</label>
            <input
              v-model="fieldSlug"
              type="text"
              placeholder="e.g. document_summary"
            />
          </div>

          <div class="form-group">
            <label>Field Data Type</label>
            <div class="type-palette">
              <button
                v-for="item in supportedTypes"
                :key="item.type"
                type="button"
                class="type-btn"
                :class="{ active: fieldType === item.type }"
                @click="fieldType = item.type"
              >
                <span>{{ item.icon }}</span>
                <span>{{ item.label }}</span>
              </button>
            </div>
          </div>

          <div class="form-group">
            <label>Extraction Prompt / Description</label>
            <textarea
              v-model="fieldDescription"
              rows="3"
              placeholder="Instructions guiding LLM metadata extraction..."
            ></textarea>
          </div>

          <div class="form-group-checkbox">
            <label>
              <input v-model="fieldRequired" type="checkbox" />
              <span>Mark this field as mandatory in validation schema</span>
            </label>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showAddFieldModal = false">Cancel</button>
          <button
            class="btn btn-primary"
            :disabled="!fieldLabel.trim() || !fieldSlug.trim()"
            @click="handleAddField"
          >
            Create Field
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.schema-designer-wrapper {
  flex: 1;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
}

.schema-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h2 {
    font-size: 22px;
    font-weight: 700;
  }

  .subtitle {
    font-size: 14px;
    color: $color-text-secondary;
    margin-top: 4px;
  }
}

.schema-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  background-color: $color-surface;
  border: 1px dashed $color-border;
  border-radius: $radius-lg;
  text-align: center;
  gap: 12px;

  .empty-icon {
    font-size: 40px;
  }

  h3 {
    font-size: 18px;
    font-weight: 600;
  }

  p {
    font-size: 14px;
    color: $color-text-secondary;
    max-width: 440px;
  }
}

.fields-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.field-card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.15s ease;

  &:hover {
    border-color: rgba(56, 189, 248, 0.4);
  }
}

.field-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.field-identity {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.type-pill {
  font-family: $font-family-mono;
  font-size: 10px;
  background-color: rgba(56, 189, 248, 0.15);
  color: $color-primary;
  padding: 2px 6px;
  border-radius: $radius-sm;
  width: fit-content;
}

.field-title {
  font-size: 15px;
  font-weight: 600;
}

.field-slug-row {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .slug-tag {
    font-family: $font-family-mono;
    font-size: 12px;
    color: $color-text-secondary;
    background-color: rgba(0, 0, 0, 0.25);
    padding: 2px 6px;
    border-radius: $radius-sm;
  }
}

.required-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: $color-text-muted;
  cursor: pointer;

  input {
    accent-color: $color-primary;
  }
}

.field-desc {
  font-size: 12px;
  color: $color-text-muted;
  line-height: 1.4;
  min-height: 32px;
}

.field-footer {
  display: flex;
  justify-content: space-between;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  padding-top: 8px;
  font-size: 10px;
  color: $color-text-muted;
  font-family: $font-family-mono;
}

.type-palette {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.type-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid $color-border;
  border-radius: $radius-md;
  color: $color-text-secondary;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background-color: $color-surface-hover;
    color: $color-text-primary;
  }

  &.active {
    background-color: rgba(56, 189, 248, 0.15);
    border-color: $color-primary;
    color: $color-primary;
    font-weight: 600;
  }
}

.form-group-checkbox {
  label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    cursor: pointer;

    input {
      accent-color: $color-primary;
    }
  }
}

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
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  width: 520px;
  max-width: 90vw;
  box-shadow: $shadow-modal;
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid $color-border;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .close-btn {
    color: $color-text-secondary;
    &:hover { color: $color-text-primary; }
  }
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 12px;
    font-weight: 600;
    color: $color-text-secondary;
    text-transform: uppercase;
  }

  input, textarea {
    background-color: rgba(0, 0, 0, 0.3);
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 8px 12px;
    color: $color-text-primary;
    outline: none;

    &:focus { border-color: $color-primary; }
  }
}

.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid $color-border;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  padding: 8px 16px;
  border-radius: $radius-md;
  font-weight: 500;
  cursor: pointer;

  &.btn-primary {
    background-color: $color-primary;
    color: #000;
    &:hover:not(:disabled) { background-color: $color-primary-hover; }
  }

  &.btn-secondary {
    background-color: $color-surface-hover;
    color: $color-text-primary;
    border: 1px solid $color-border;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: $color-text-muted;

  &.btn-danger:hover {
    color: $color-status-missing;
  }
}
</style>