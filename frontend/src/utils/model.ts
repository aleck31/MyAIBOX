interface ModelOption { model_id: string }

/**
 * Pick the initial model for a module's selector.
 *
 * Prefers the module's configured default; only falls back to the first model
 * in the list (which is alphabetical, so it would otherwise pick e.g. Haiku
 * over Sonnet) when no valid default is set.
 */
export function resolveDefaultModel(
  models: ModelOption[],
  defaultModel?: string,
): string {
  if (!models.length) return ''
  if (defaultModel && models.some(m => m.model_id === defaultModel)) return defaultModel
  return models[0].model_id
}
