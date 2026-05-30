export interface SessionInfo {
  module: string
  session_id: string
  records: number
  created: string
  updated: string
}

// Model-agnostic thinking intent; backend translates to each model's wire format.
export interface ThinkingConfig {
  enabled?: boolean
  effort?: string  // low | medium | high | xhigh | max
}

export interface ModuleConfig {
  default_model: string
  parameters: string
  enabled_tools: string[]
  thinking?: ThinkingConfig
  // The module's own eligible models (filtered server-side); ModuleCard uses these.
  models?: Array<{ model_id: string; name: string; reasoning?: boolean }>
}

export interface ModulesData {
  modules: Record<string, ModuleConfig>
  model_choices: Array<{ model_id: string; name: string; reasoning?: boolean }>
  available_tools: string[]
}
