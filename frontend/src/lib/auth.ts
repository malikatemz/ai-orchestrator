const AUTH_TOKEN_KEY = 'ai_orchestrator_api_token'

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_API_TOKEN || null
  }

  return window.localStorage.getItem(AUTH_TOKEN_KEY) || process.env.NEXT_PUBLIC_API_TOKEN || null
}

export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, token)
}

export function clearAuthToken(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
}
