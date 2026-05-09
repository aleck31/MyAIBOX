import { redirectToLogin } from '../auth'

/**
 * Global fetch wrapper with auth guard.
 * All API calls should use this instead of raw fetch().
 */
export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, { credentials: 'include', ...init })
  if (res.status === 401 && !path.includes('/auth/')) {
    redirectToLogin()
    throw new Error('Session expired')
  }
  return res
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return authFetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export async function getMe(): Promise<{ sub: string; username: string; email: string } | null> {
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

// ─── Chat (unified agent/persona) ────────────────────────────────────────────

const CHAT = '/api/chat'

export interface ChatAgent {
  id: string
  name: string
  description: string
  avatar: string
  default_model: string | null
  preset_questions: string[]
  enabled_legacy_tools: string[]
  enabled_builtin_tools: string[]
  enabled_mcp_servers: string[]
  enabled_skills: string[]
  parameters: Record<string, unknown>
  workspace_enabled: boolean
  order: number
}

export interface ChatSession {
  session_id: string
  model_id: string | null
  cloud_sync: boolean
  history: Array<{ role: 'user' | 'assistant'; content: unknown }>
}

export interface WorkspaceFile {
  name: string
  size: number
  mtime: number
}

// Agent registry --------------------------------------------------------------

export async function listChatAgents(): Promise<{ agents: ChatAgent[] }> {
  const res = await apiFetch(`${CHAT}/agents`)
  return res.json()
}

export async function getChatAgent(agentId: string): Promise<ChatAgent> {
  const res = await apiFetch(`${CHAT}/agents/${encodeURIComponent(agentId)}`)
  if (!res.ok) throw new Error(`Agent ${agentId} not found`)
  return res.json()
}

export async function patchChatAgent(agentId: string, patch: Partial<ChatAgent>): Promise<ChatAgent> {
  const res = await apiFetch(`${CHAT}/agents/${encodeURIComponent(agentId)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
  return res.json()
}

export async function resetChatAgent(agentId: string): Promise<ChatAgent> {
  const res = await apiFetch(`${CHAT}/agents/${encodeURIComponent(agentId)}/reset`, { method: 'POST' })
  return res.json()
}

export async function listChatSkills(): Promise<{ skills: Array<{ name: string; description: string }> }> {
  const res = await apiFetch(`${CHAT}/skills`)
  return res.json()
}

// Session per agent -----------------------------------------------------------

export async function getChatSession(agentId: string): Promise<ChatSession> {
  const res = await apiFetch(`${CHAT}/session?agent_id=${encodeURIComponent(agentId)}`)
  if (!res.ok) throw new Error('Session load failed')
  return res.json()
}

export async function updateChatModel(agentId: string, model_id: string) {
  const res = await apiFetch(`${CHAT}/session/model?agent_id=${encodeURIComponent(agentId)}`, {
    method: 'POST',
    body: JSON.stringify({ model_id }),
  })
  return res.json()
}

export async function updateChatCloudSync(agentId: string, enabled: boolean) {
  const res = await apiFetch(`${CHAT}/session/cloud-sync?agent_id=${encodeURIComponent(agentId)}`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
  return res.json()
}

export async function syncChatHistory(agentId: string, messages: Array<{ role: string; content: unknown }>) {
  const res = await apiFetch(`${CHAT}/session/history?agent_id=${encodeURIComponent(agentId)}`, {
    method: 'POST',
    body: JSON.stringify({ messages }),
  })
  return res.json()
}

export async function clearChatHistory(agentId: string) {
  const res = await apiFetch(`${CHAT}/session/history?agent_id=${encodeURIComponent(agentId)}`, {
    method: 'DELETE',
  })
  return res.json()
}

// Workspace per agent ---------------------------------------------------------

export async function listChatWorkspace(agentId: string): Promise<{ files: WorkspaceFile[] }> {
  const res = await apiFetch(`${CHAT}/workspace?agent_id=${encodeURIComponent(agentId)}`)
  return res.json()
}

export function chatWorkspaceFileUrl(agentId: string, name: string): string {
  return `${CHAT}/workspace/${encodeURIComponent(name)}?agent_id=${encodeURIComponent(agentId)}`
}

export async function deleteChatWorkspaceFile(agentId: string, name: string) {
  const res = await apiFetch(
    `${CHAT}/workspace/${encodeURIComponent(name)}?agent_id=${encodeURIComponent(agentId)}`,
    { method: 'DELETE' },
  )
  return res.json()
}

export const chatStreamUrl = `${CHAT}/stream`

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

export async function getModels({ refresh = false }: { refresh?: boolean } = {}) {
  const url = refresh ? `${SETTINGS}/models?refresh=true` : `${SETTINGS}/models`
  const res = await apiFetch(url)
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
