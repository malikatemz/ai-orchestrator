import React from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

let mockToken = ''

vi.mock('../../lib/auth', () => ({
  getAuthToken: () => mockToken,
  setAuthToken: (newToken: string) => {
    mockToken = newToken
  },
  clearAuthToken: () => {
    mockToken = ''
  },
}))

import { AuthPanel } from './AuthPanel'

describe('AuthPanel', () => {
  beforeEach(() => {
    mockToken = ''
  })

  it('shows placeholder and allows token save/clear', () => {
    render(<AuthPanel />)

    const input = screen.getByPlaceholderText('Enter API token') as HTMLInputElement
    expect(input).toBeTruthy()

    fireEvent.change(input, { target: { value: 'my-token' } })
    fireEvent.click(screen.getByText('Save token'))

    expect(screen.getByText('Saved credentials. Refresh the page to apply changes.')).toBeTruthy()
  })

  it('clears API token', () => {
    render(<AuthPanel />)

    fireEvent.click(screen.getByText('Clear token'))
    expect(screen.getByText('API token cleared, unauthenticated mode enabled.')).toBeTruthy()
  })

  it('shows error for empty token', () => {
    mockToken = 'existing-token' // Set existing token for this test
    render(<AuthPanel />)

    // Clear the existing token from input
    const input = screen.getByPlaceholderText('Enter API token') as HTMLInputElement
    act(() => {
      fireEvent.change(input, { target: { value: '' } })
    })
    
    // Now try to save
    act(() => {
      fireEvent.click(screen.getByText('Save token'))
    })
    expect(screen.getByText('API token is required to authenticate with the backend.')).toBeTruthy()
  })
})
