export interface SessionInfo {
  module: string
  session_id: string
  records: number
  created: string
  updated: string
}

export interface ModuleConfig {
  default_model: string
  parameters: string
  enabled_tools: string[]
}

export interface ModulesData {
  modules: Record<string, ModuleConfig>
  model_choices: Array<{ model_id: string; name: string }>
  available_tools: string[]
}
