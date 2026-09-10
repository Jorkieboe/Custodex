<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { type SchemaField } from '../../services/api'
import FieldCard from './FieldCard.vue'

const store = useWorkspaceStore()
const showJsonPreview = ref(false)

const paletteTypes = [
  { type: 'string', label: 'Text', icon: '🔤', desc: 'String value' },
  { type: 'number', label: 'Number', icon: '🔢', desc: 'Numeric quantity or rating' },
  { type: 'boolean', label: 'Boolean', icon: '🔘', desc: 'True / false flag' },
  { type: 'array[string]', label: 'Tag List', icon: '🏷️', desc: 'Array of strings' },
  { type: 'array[number]', label: 'Number List', icon: '📊', desc: 'Array of numbers' },
  { type: 'date', label: 'Date', icon: '📅', desc: 'ISO Date string' }
] as const

async function handleAddField(type: SchemaField['field_type']) {
  const defaultLabels: Record<string, string> = {
    string: 'Summary Topic',
    number: 'Confidence Score',
    boolean: 'Is Verified',
    'array[string]': 'Key Entities',
    'array[number]': 'Data Metrics',
    date: 'Publication Date'
  }

  await store.addSchemaField({
    field_label: defaultLabels[type] || 'New Field',
    field_type: type,
    description: `Extract or identify ${defaultLabels[type] || 'attribute'} from chunk`,
    is_required: false
  })
}

async function handleUpdateField(fieldId: string, data: Partial<SchemaField>) {
  await store.modifySchemaField(fieldId, data)
}

async function handleDeleteField(fieldId: string) {
  await store.removeSchemaField(fieldId)
}

async function handleMoveUp(fieldId: string) {
  const idx = store.schemaFields.findIndex((f) => f.id === fieldId)
  if (idx <= 0) return
  const newFields = [...store.schemaFields]
  const temp = newFields[idx]
  newFields[idx] = newFields[idx - 1]
  newFields[idx - 1] = temp
  await store.reorderSchemaFields(newFields)
}

async function handleMoveDown(fieldId: string) {
  const idx = store.schemaFields.findIndex((f) => f.id === fieldId)
  if (idx === -1 || idx >= store.schemaFields.length - 1) return
  const newFields = [...store.schemaFields]
  const temp = newFields[idx]
  newFields[idx] = newFields[idx + 1]
  newFields[idx + 1] = temp
  await store.reorderSchemaFields(newFields)
}

const compiledJsonSchema = computed(() => {
  const properties: Record<string, any> = {}
  const required: string[] = []

  for (const field of store.schemaFields) {
    const slug = field.field_slug || `field_${field.id.slice(0, 8)}`
    const propDef: Record<string, any> = {}

    if (field.description) {
      propDef.description = field.description
    }

    if (field.field_type === 'string') {
      propDef.type = 'string'
    } else if (field.field_type === 'number') {
      propDef.type = 'number'
    } else if (field.field_type === 'boolean') {
      propDef.type = 'boolean'
    } else if (field.field_type === 'date') {
      propDef.type = 'string'
      propDef.format = 'date'
    } else if (field.field_type === 'array[string]') {
      propDef.type = 'array'
      propDef.items = { type: 'string' }
    } else if (field.field_type === 'array[number]') {
      propDef.type = 'array'
      propDef.items = { type: 'number' }
    }

    properties[slug] = propDef

    if (field.is_required) {
      required.push(slug)
    }
  }

  const schema: Record<string, any> = {
    $schema: 'http://json-schema.org/draft-07/schema#',
    type: 'object',
    properties,
    additionalProperties: false
  }

  if (required.length > 0) {
    schema.required = required
  }

  return JSON.stringify(schema, null, 2)
})
</script>

<template>
  <div class="schema-designer-layout">
    <!-- Main Palette & Fields Column -->
    <div class="designer-main">
      <div class="designer-header">
        <div>
          <h2>CMS Metadata Schema Designer</h2>
          <p class="subtitle">
            Configure structured metadata fields. Each field is tracked by an immutable UUID so renames will never break chunk links.
          </p>
        </div>

        <div class="header-actions">
          <button
            class="btn btn-secondary"
            @click="showJsonPreview = !showJsonPreview"
          >
            {{ showJsonPreview ? 'Hide JSON Schema' : 'View JSON Schema' }}
          </button>
          <button
            class="btn btn-primary"
            :disabled="store.schemaFields.length === 0"
            @click="store.openBatchModal"
          >
            ⚡ Extract Metadata
          </button>
        </div>
      </div>

      <!-- Field Type Palette -->
      <div class="palette-container">
        <span class="palette-label">Add Field Type:</span>
        <div class="palette-grid">
          <button
            v-for="item in paletteTypes"
            :key="item.type"
            class="palette-card"
            @click="handleAddField(item.type)"
          >
            <span class="palette-icon">{{ item.icon }}</span>
            <span class="palette-name">{{ item.label }}</span>
          </button>
        </div>
      </div>

      <!-- Active Fields List -->
      <div class="fields-container">
        <div v-if="store.schemaFields.length === 0" class="empty-schema">
          <span class="empty-icon">📐</span>
          <p class="empty-title">No schema fields configured</p>
          <span class="empty-hint">Click any field type above to begin building your metadata template.</span>
        </div>

        <div v-else class="fields-list">
          <FieldCard
            v-for="(field, idx) in store.schemaFields"
            :key="field.id"
            :field="field"
            :is-first="idx === 0"
            :is-last="idx === store.schemaFields.length - 1"
            @update="handleUpdateField"
            @delete="handleDeleteField"
            @move-up="handleMoveUp"
            @move-down="handleMoveDown"
          />
        </div>
      </div>
    </div>

    <!-- JSON Schema Drawer -->
    <aside v-if="showJsonPreview" class="json-schema-drawer">
      <div class="drawer-header">
        <h3>Compiled JSON Schema</h3>
        <button class="btn-close" @click="showJsonPreview = false">✕</button>
      </div>
      <p class="drawer-desc">This JSON Schema contract is supplied to LM Studio completions.</p>
      <pre class="json-preview"><code>{{ compiledJsonSchema }}</code></pre>
    </aside>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.schema-designer-layout {
  display: flex;
  flex: 1;
  height: calc(100vh - #{$header-height});
  background-color: $color-bg;
  overflow: hidden;
}

.designer-main {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.designer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;

  h2 {
    font-size: 22px;
    font-weight: 700;
  }

  .subtitle {
    font-size: 13px;
    color: $color-text-secondary;
    margin-top: 4px;
    max-width: 600px;
  }
}

.palette-container {
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid $color-border;
  border-radius: $radius-md;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.palette-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: $color-text-muted;
}

.palette-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}

.palette-card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-sm;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    border-color: $color-primary;
    background-color: $color-surface-hover;
    transform: translateY(-1px);
  }

  .palette-icon {
    font-size: 18px;
  }

  .palette-name {
    font-size: 12px;
    font-weight: 600;
    color: $color-text-primary;
  }
}

.fields-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fields-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-schema {
  background-color: $color-surface;
  border: 1px dashed $color-border;
  border-radius: $radius-lg;
  padding: 48px 24px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;

  .empty-icon {
    font-size: 32px;
  }

  .empty-title {
    font-size: 15px;
    font-weight: 600;
  }

  .empty-hint {
    font-size: 13px;
    color: $color-text-muted;
  }
}

.json-schema-drawer {
  width: 380px;
  background-color: $color-surface;
  border-left: 1px solid $color-border;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h3 {
    font-size: 15px;
    font-weight: 600;
  }

  .btn-close {
    color: $color-text-secondary;
    font-size: 14px;
    &:hover { color: $color-text-primary; }
  }
}

.drawer-desc {
  font-size: 12px;
  color: $color-text-muted;
}

.json-preview {
  flex: 1;
  background-color: rgba(0, 0, 0, 0.4);
  border: 1px solid $color-border;
  border-radius: $radius-sm;
  padding: 12px;
  overflow: auto;
  font-family: $font-family-mono;
  font-size: 11px;
  color: $color-primary;
  line-height: 1.4;
}

.btn {
  padding: 6px 14px;
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
}
</style>