/**
 * Auth-mode helpers. Values are baked in at build time via vite define.
 */
export const SSO_ENABLED: boolean = __SSO_ENABLED__
export const SSO_AUTH_ORIGIN: string = __SSO_AUTH_ORIGIN__
export const SSO_PROVIDER_NAME: string = __SSO_PROVIDER_NAME__

export function buildLoginUrl(returnTo: string = window.location.href): string {
  if (SSO_ENABLED) {
    return `${SSO_AUTH_ORIGIN}/login?redirect=${encodeURIComponent(returnTo)}`
  }
  return '/login'
}

export function buildLogoutUrl(): string {
  return SSO_ENABLED ? `${SSO_AUTH_ORIGIN}/logout` : '/login'
}

export function redirectToLogin(returnTo?: string): void {
  window.location.href = buildLoginUrl(returnTo)
}
