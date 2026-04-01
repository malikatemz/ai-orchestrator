import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL || 'https://example.com').replace(/\/$/, '')
let indexableSiteUrl = false

try {
  const parsedUrl = new URL(siteUrl)
  indexableSiteUrl = parsedUrl.protocol === 'https:' && !['localhost', '127.0.0.1', 'example.com'].includes(parsedUrl.hostname)
} catch {
  indexableSiteUrl = false
}
const buildDate = new Date().toISOString()

const routes = [
  '/',
  '/ai-workflow-orchestration',
  '/multi-agent-orchestration',
  '/ai-operations-dashboard',
  '/ai-workflow-automation-use-cases',
  '/ai-agent-monitoring-checklist',
]

const publicDir = resolve(process.cwd(), 'public')
mkdirSync(publicDir, { recursive: true })

const robotsTxt = indexableSiteUrl
  ? `User-agent: *
Allow: /

Sitemap: ${siteUrl}/sitemap.xml
`
  : `User-agent: *
Disallow: /
`

const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${(indexableSiteUrl ? routes : [])
  .map((route, index) => {
    const priority = index === 0 ? '1.0' : '0.9'
    return `  <url>
    <loc>${siteUrl}${route}</loc>
    <lastmod>${buildDate}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>${priority}</priority>
  </url>`
  })
  .join('\n')}
</urlset>
`

writeFileSync(resolve(publicDir, 'robots.txt'), robotsTxt)
writeFileSync(resolve(publicDir, 'sitemap.xml'), sitemapXml)
