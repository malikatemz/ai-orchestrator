import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL || 'https://example.com').replace(/\/$/, '')

const routes = [
  '/',
  '/ai-workflow-orchestration',
  '/multi-agent-orchestration',
  '/ai-operations-dashboard',
  '/ai-workflow-automation-use-cases',
  '/ai-agent-monitoring-checklist',
  '/platform-ops',
]

const publicDir = resolve(process.cwd(), 'public')
mkdirSync(publicDir, { recursive: true })

const robotsTxt = `User-agent: *
Allow: /

Sitemap: ${siteUrl}/sitemap.xml
`

const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${routes
  .map((route, index) => {
    const priority = index === 0 ? '1.0' : '0.9'
    return `  <url>
    <loc>${siteUrl}${route}</loc>
    <changefreq>weekly</changefreq>
    <priority>${priority}</priority>
  </url>`
  })
  .join('\n')}
</urlset>
`

writeFileSync(resolve(publicDir, 'robots.txt'), robotsTxt)
writeFileSync(resolve(publicDir, 'sitemap.xml'), sitemapXml)
