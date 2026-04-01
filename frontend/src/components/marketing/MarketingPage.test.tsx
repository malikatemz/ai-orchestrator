import React from 'react'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { marketingPages } from '../../content/marketingPages'
import { MarketingPage } from './MarketingPage'

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a>,
}))

vi.mock('../common/SeoHead', () => ({
  SeoHead: () => null,
}))

describe('MarketingPage', () => {
  it('renders the workflow orchestration marketing page content', () => {
    render(<MarketingPage content={marketingPages.workflow} />)

    expect(screen.getByText('AI workflow orchestration for teams that need reliability, not just demos.')).toBeTruthy()
    expect(screen.getByText('What AI workflow orchestration should solve')).toBeTruthy()
  })

  it('renders route navigation links in the shared marketing layout', () => {
    render(<MarketingPage content={marketingPages.operations} />)

    expect(screen.getAllByRole('link', { name: /Platform Home/ }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /Workflow Orchestration/ }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /AI Operations Dashboard/ }).length).toBeGreaterThan(0)
  })
})
