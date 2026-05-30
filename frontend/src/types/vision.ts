export interface VisionConfig {
  models: Array<{ model_id: string; name: string }>
  default_model?: string
}
