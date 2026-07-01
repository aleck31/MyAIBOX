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

/**
 * Keep `current` if it's still a valid choice, otherwise fall back to the default.
 *
 * A stored/session model can go stale when it's disabled or removed from the registry; submitting the dead id then fails with "model not found". 
 * Call this after loading the model list so a module never holds an invalid selection.
 * Returns '' only when the list is empty.
 */
export function ensureValidModel(
  current: string | null | undefined,
  models: ModelOption[],
  defaultModel?: string | null,
): string {
  if (current && models.some(m => m.model_id === current)) return current
  return resolveDefaultModel(models, defaultModel ?? undefined)
}
