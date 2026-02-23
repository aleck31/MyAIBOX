/**
 * Fetch wrapper that includes session cookies for auth.
 */

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  return res
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export async function getMe(): Promise<{ username: string } | null> {
  const res = await apiFetch('/api/auth/me')
  if (!res.ok) return null
  return res.json()
}

export async function loginApi(username: string, password: string) {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)

  const res = await fetch('/api/auth/login', {
    method: 'POST',
    body: formData,
    credentials: 'include',
    // No Content-Type header — let browser set multipart/form-data boundary
  })
  return res.json()
}

export async function logoutApi() {
  const res = await apiFetch('/api/auth/logout', { method: 'POST' })
  return res.ok
}

// ─── Assistant ───────────────────────────────────────────────────────────────

const ASSISTANT = '/api/assistant'

export async function getAssistantConfig() {
  const res = await apiFetch(`${ASSISTANT}/config`)
  return res.json()
}

export async function getAssistantSession() {
  const res = await apiFetch(`${ASSISTANT}/session`)
  if (!res.ok) throw new Error('Session load failed')
  return res.json()
}

export async function updateAssistantModel(model_id: string) {
  const res = await apiFetch(`${ASSISTANT}/session/model`, {
    method: 'POST',
    body: JSON.stringify({ model_id }),
  })
  return res.json()
}

export async function syncAssistantHistory(messages: Array<{ role: string; content: unknown }>) {
  const res = await apiFetch(`${ASSISTANT}/session/history`, {
    method: 'POST',
    body: JSON.stringify({ messages }),
  })
  return res.json()
}

export async function updateAssistantCloudSync(enabled: boolean) {
  const res = await apiFetch(`${ASSISTANT}/session/cloud-sync`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
  return res.json()
}

// ─── Persona ─────────────────────────────────────────────────────────────────

const PERSONA = '/api/persona'

export async function getConfig() {
  const res = await apiFetch(`${PERSONA}/config`)
  return res.json()
}

export async function getSession() {
  const res = await apiFetch(`${PERSONA}/session`)
  if (!res.ok) throw new Error('Session load failed')
  return res.json()
}

export async function updateRole(persona_role: string) {
  const res = await apiFetch(`${PERSONA}/session/role`, {
    method: 'POST',
    body: JSON.stringify({ persona_role }),
  })
  return res.json()
}

export async function updateSessionModel(model_id: string) {
  const res = await apiFetch(`${PERSONA}/session/model`, {
    method: 'POST',
    body: JSON.stringify({ model_id }),
  })
  return res.json()
}

export async function syncHistory(messages: Array<{ role: string; content: unknown }>) {
  const res = await apiFetch(`${PERSONA}/session/history`, {
    method: 'POST',
    body: JSON.stringify({ messages }),
  })
  return res.json()
}

export async function updateCloudSync(enabled: boolean) {
  const res = await apiFetch(`${PERSONA}/session/cloud-sync`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
  return res.json()
}

// ─── Text ────────────────────────────────────────────────────────────────────

const TEXT = '/api/text'

export async function getTextConfig() {
  const res = await apiFetch(`${TEXT}/config`)
  return res.json()
}

// ─── Summary ─────────────────────────────────────────────────────────────────

const SUMMARY = '/api/summary'

export async function getSummaryConfig() {
  const res = await apiFetch(`${SUMMARY}/config`)
  return res.json()
}

// ─── Asking ──────────────────────────────────────────────────────────────────

const ASKING = '/api/asking'

export async function getAskingConfig() {
  const res = await apiFetch(`${ASKING}/config`)
  return res.json()
}

// ─── Vision ──────────────────────────────────────────────────────────────────

const VISION = '/api/vision'

export async function getVisionConfig() {
  const res = await apiFetch(`${VISION}/config`)
  return res.json()
}

// ─── Draw ────────────────────────────────────────────────────────────────────

const DRAW = '/api/draw'

export async function getDrawConfig() {
  const res = await apiFetch(`${DRAW}/config`)
  return res.json()
}

// ─── Settings ────────────────────────────────────────────────────────────────

const SETTINGS = '/api/settings'

export async function getSettingsSessions() {
  const res = await apiFetch(`${SETTINGS}/sessions`)
  return res.json()
}

export async function deleteSession(sessionId: string) {
  const res = await apiFetch(`${SETTINGS}/sessions/${sessionId}`, { method: 'DELETE' })
  return res.json()
}

export async function clearSessionHistory(sessionId: string) {
  const res = await apiFetch(`${SETTINGS}/sessions/clear-history`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  })
  return res.json()
}

export async function getModulesConfig() {
  const res = await apiFetch(`${SETTINGS}/modules`)
  return res.json()
}

export async function updateModuleConfig(moduleName: string, config: { default_model: string; parameters: string; enabled_tools: string[] }) {
  const res = await apiFetch(`${SETTINGS}/modules/update`, {
    method: 'POST',
    body: JSON.stringify({ module_name: moduleName, ...config }),
  })
  return res.json()
}

export async function getModels() {
  const res = await apiFetch(`${SETTINGS}/models`)
  return res.json()
}

export async function addModel(data: Record<string, unknown>) {
  const res = await apiFetch(`${SETTINGS}/models/add`, { method: 'POST', body: JSON.stringify(data) })
  return res.json()
}

export async function updateModel(data: Record<string, unknown>) {
  const res = await apiFetch(`${SETTINGS}/models/update`, { method: 'POST', body: JSON.stringify(data) })
  return res.json()
}

export async function deleteModel(modelId: string) {
  const res = await apiFetch(`${SETTINGS}/models/${encodeURIComponent(modelId)}`, { method: 'DELETE' })
  return res.json()
}

export async function getMcpServers() {
  const res = await apiFetch(`${SETTINGS}/mcp-servers`)
  return res.json()
}

export async function addMcpServer(data: { name: string; type: string; url: string; args: string }) {
  const res = await apiFetch(`${SETTINGS}/mcp-servers/add`, { method: 'POST', body: JSON.stringify(data) })
  return res.json()
}

export async function deleteMcpServer(name: string) {
  const res = await apiFetch(`${SETTINGS}/mcp-servers/${encodeURIComponent(name)}`, { method: 'DELETE' })
  return res.json()
}

export async function toggleMcpServer(name: string, disabled: boolean) {
  const res = await apiFetch(`${SETTINGS}/mcp-servers/toggle`, { method: 'POST', body: JSON.stringify({ name, disabled }) })
  return res.json()
}
