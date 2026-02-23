export interface ModelOption {
  model_id: string
  name: string
}

export interface PersonaRole {
  key: string
  display_name: string
}

export interface PersonaConfig {
  models: ModelOption[]
  persona_roles: PersonaRole[]
}

export interface PersonaPrefs {
  session_id: string
  model_id: string | null
  persona_role: string
  cloud_sync: boolean
  history: ChatMessage[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
