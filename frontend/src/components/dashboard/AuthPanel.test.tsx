import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../lib/auth', () => {
  let token = ''
  return {
    getAuthToken: () => token,
    setAuthToken: (newToken: string) => {
      token = newToken
    },
    clearAuthToken: () => {
      token = ''
    },
  }
})

const windowReload = vi.spyOn(window.location, 'reload').mockImplementation(() => undefined)

import { AuthPanel } from './AuthPanel'

describe('AuthPanel', () => {
  it('shows placeholder and allows token save/clear', () => {
    render(<AuthPanel />)

    const input = screen.getByPlaceholderText('Enter API token') as HTMLInputElement
    expect(input).toBeTruthy()

    fireEvent.change(input, { target: { value: 'my-token' } })
    fireEvent.click(screen.getByText('Save token'))

    expect(windowReload).toHaveBeenCalled()
  })

  it('clears API token', () => {
    render(<AuthPanel />)

    fireEvent.click(screen.getByText('Clear token'))
    expect(windowReload).toHaveBeenCalledTimes(2)
  })
})
