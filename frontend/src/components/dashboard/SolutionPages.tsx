import React from 'react'
import Link from 'next/link'

import { marketingRoutes } from '../../lib/routes'

export function SolutionPages() {
  return (
    <section id="solution-pages" className="panel prose-card">
      <div className="section-header">
        <div>
          <p className="eyebrow">SEO route structure</p>
          <h2>Explore the main solution pages</h2>
        </div>
      </div>
      <div className="route-grid">
        {marketingRoutes.filter((route) => route.href !== '/').map((route) => (
          <Link key={route.href} href={route.href} className="route-card">
            <strong>{route.label}</strong>
            <span>{route.description}</span>
          </Link>
        ))}
      </div>
    </section>
  )
}
