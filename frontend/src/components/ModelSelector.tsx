import type { ModelOption } from '../types/persona'

interface ModelSelectorProps {
  models: ModelOption[]
  value: string | null
  onChange: (modelId: string) => void
  disabled?: boolean
}

export default function ModelSelector({ models, value, onChange, disabled }: ModelSelectorProps) {
  return (
    <select
      className="select"
      value={value ?? ''}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      style={{ maxWidth: '200px' }}
      title="Select model"
    >
      {!value && (
        <option value="" disabled>
          Select model…
        </option>
      )}
      {models.map((m) => (
        <option key={m.model_id} value={m.model_id}>
          {m.name}
        </option>
      ))}
    </select>
  )
}
