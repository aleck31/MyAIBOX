/** The APIs a model can be called with (`LLMModel.api` on the server), in display order. */
export const API_LABELS: Record<string, string> = {
  'bedrock-converse': 'Bedrock Converse',
  'bedrock-invoke': 'Bedrock InvokeModel',
  'bedrock-bidi-stream': 'Bedrock Bidirectional Stream',
  'anthropic-messages': 'Anthropic Messages',
  'openai-responses': 'OpenAI Responses',
  'openai-chat-completions': 'OpenAI Chat Completions',
  'gemini': 'Gemini',
}

export const BEDROCK_APIS = ['bedrock-converse', 'bedrock-invoke', 'bedrock-bidi-stream']

export const apiLabel = (api: string) => API_LABELS[api] ?? api

export interface ProviderInfo {
  name: string
  auth: 'aws' | 'api_key'
  apis: string[]
  base_url: string
  region: string
  secret_name: string
  has_api_key: boolean
  models: string[]
}
