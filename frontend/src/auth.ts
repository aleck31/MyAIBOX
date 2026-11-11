/**
 * Myners SSO, the only way to log in (standards/SSO-INTEGRATION-GUIDE.md). Login and logout happen on the auth
 * service; this app never sees a password or a token. Values are baked in at build time via vite define.
 */
export const SSO_AUTH_ORIGIN: string = __SSO_AUTH_ORIGIN__
export const SSO_PROVIDER_NAME: string = __SSO_PROVIDER_NAME__

export function buildLoginUrl(returnTo: string = window.location.href): string {
  return `${SSO_AUTH_ORIGIN}/login?redirect=${encodeURIComponent(returnTo)}`
}

/** Logs out of every *.myners.net app, then lands on this app's sign-in page. */
export function buildLogoutUrl(): string {
  return `${SSO_AUTH_ORIGIN}/logout?post_logout_redirect=${encodeURIComponent(`${window.location.origin}/login`)}`
}

export function redirectToLogin(returnTo?: string): void {
  window.location.href = buildLoginUrl(returnTo)
}
