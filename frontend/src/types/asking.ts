export interface AskingConfig {
  models: Array<{ model_id: string; name: string }>
  default_model?: string
}

export interface AskingHistory {
  role: 'user' | 'assistant'
  content: string
}
