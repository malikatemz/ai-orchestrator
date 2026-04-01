import { useEffect, useMemo, useState } from 'react'
import { getAuthToken, setAuthToken, clearAuthToken } from '../../lib/auth'

export function AuthPanel() {
  const [token, setToken] = useState('')
  const [savedToken, setSavedToken] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const existingToken = getAuthToken() || ''
    setToken(existingToken)
    setSavedToken(existingToken)
  }, [])

  const isDirty = useMemo(() => token !== savedToken, [token, savedToken])

  const handleSave = () => {
    if (!token.trim()) {
      setMessage('API token is required to authenticate with the backend.')
      return
    }

    setAuthToken(token.trim())
    setSavedToken(token.trim())
    setMessage('Saved credentials. Refreshing data in a moment...')
    window.location.reload()
  }

  const handleClear = () => {
    clearAuthToken()
    setToken('')
    setSavedToken('')
    setMessage('API token cleared, unauthenticated mode enabled.')
    window.location.reload()
  }

  return (
    <section className="panel auth-panel">
      <div className="section-header">
        <p className="eyebrow">API Authentication</p>
        <h2>Authenticated Access</h2>
      </div>

      <p className="muted">Provide your API token to access secured orchestrator endpoints (required in production).</p>

      <div className="auth-grid">
        <input
          className="input"
          type="password"
          aria-label="API token"
          value={token}
          placeholder="Enter API token"
          onChange={(event) => setToken(event.target.value)}
        />

        <div className="actions">
          <button className="btn" type="button" onClick={handleSave} disabled={!isDirty}>
            Save token
          </button>
          <button className="btn btn-muted" type="button" onClick={handleClear}>
            Clear token
          </button>
        </div>
      </div>

      {message ? <p className="muted">{message}</p> : null}
    </section>
  )
}
