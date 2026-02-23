export interface AssistantConfig {
  models: Array<{ model_id: string; name: string }>
}

export interface AssistantPrefs {
  session_id: string
  model_id: string | null
  cloud_sync: boolean
  history: Array<{ role: 'user' | 'assistant'; content: unknown }>
}
