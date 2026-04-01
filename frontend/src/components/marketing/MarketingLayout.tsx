import React, { type PropsWithChildren } from 'react'
import Link from 'next/link'

import { SeoHead } from '../common/SeoHead'
import { marketingRoutes } from '../../lib/routes'

interface MarketingLayoutBaseProps {
  title: string
  description: string
  path: string
  eyebrow: string
  heading: string
  intro: string
}

type MarketingLayoutProps = PropsWithChildren<MarketingLayoutBaseProps>

export function MarketingLayout({ title, description, path, eyebrow, heading, intro, children }: MarketingLayoutProps) {
  return (
    <>
      <SeoHead title={title} description={description} path={path} />

      <main className="marketing-shell">
        <header className="panel top-nav">
          <Link href="/" className="brand-mark">
            AI Orchestrator
          </Link>
          <nav className="top-links" aria-label="Primary">
            {marketingRoutes.map((route) => (
              <Link key={route.href} href={route.href}>
                {route.label}
              </Link>
            ))}
          </nav>
        </header>

        <section className="panel marketing-hero">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{heading}</h1>
          <p className="lead">{intro}</p>
        </section>

        {children}

        <footer className="panel marketing-footer">
          <h2>Explore the platform</h2>
          <div className="route-grid">
            {marketingRoutes.map((route) => (
              <Link key={route.href} href={route.href} className="route-card">
                <strong>{route.label}</strong>
                <span>{route.description}</span>
              </Link>
            ))}
          </div>
        </footer>
      </main>
    </>
  )
}
