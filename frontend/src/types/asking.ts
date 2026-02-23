export interface AskingConfig {
  models: Array<{ model_id: string; name: string }>
}

export interface AskingHistory {
  role: 'user' | 'assistant'
  content: string
}
