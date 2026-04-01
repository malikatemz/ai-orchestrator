import { SITE_URL } from './env'
import { coreRoutes } from './routes'

export interface SeoMetadata {
  title: string
  description: string
  path: string
  keywords?: string
}

export interface FaqSchemaItem {
  question: string
  answer: string
}

function isUnsafeHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === 'example.com'
}

export function isIndexableSiteUrl(url: string = SITE_URL): boolean {
  try {
    const parsed = new URL(url)
    return (parsed.protocol === 'https:' || parsed.hostname === 'localhost') && !isUnsafeHostname(parsed.hostname)
  } catch {
    return false
  }
}

export function buildCanonicalUrl(path: string, siteUrl: string = SITE_URL): string | null {
  if (!isIndexableSiteUrl(siteUrl)) {
    return null
  }
  return `${siteUrl}${path}`
}

export function buildRobotsContent(noindex = false, siteUrl: string = SITE_URL): string {
  if (noindex || !isIndexableSiteUrl(siteUrl)) {
    return 'noindex,follow,max-image-preview:large'
  }
  return 'index,follow,max-image-preview:large'
}

export function buildOrganizationSchema(siteUrl: string = SITE_URL) {
  if (!isIndexableSiteUrl(siteUrl)) {
    return null
  }
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'AI Orchestrator',
    url: siteUrl,
    sameAs: [siteUrl],
  }
}

export function buildSoftwareApplicationSchema(metadata: SeoMetadata, siteUrl: string = SITE_URL) {
  const canonical = buildCanonicalUrl(metadata.path, siteUrl)
  if (!canonical) {
    return null
  }
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: metadata.title,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    description: metadata.description,
    url: canonical,
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
  }
}

export function buildBreadcrumbSchema(path: string, siteUrl: string = SITE_URL) {
  if (!isIndexableSiteUrl(siteUrl)) {
    return null
  }
  const routes = coreRoutes.filter((route) => route.href === '/' || route.href === path)
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: routes.map((route, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: route.label,
      item: buildCanonicalUrl(route.href, siteUrl),
    })),
  }
}

export function buildFaqSchema(items: FaqSchemaItem[], siteUrl: string = SITE_URL) {
  if (!isIndexableSiteUrl(siteUrl) || items.length === 0) {
    return null
  }
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.answer,
      },
    })),
  }
}
