export interface TextConfig {
  operations: Array<{ key: string; label: string }>
  languages: string[]
  styles: string[]
  models: Array<{ model_id: string; name: string }>
}
