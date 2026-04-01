import { SITE_URL } from './env'
import { coreRoutes } from './routes'

export interface SeoMetadata {
  title: string
  description: string
  path: string
  keywords?: string
}

export function buildCanonicalUrl(path: string): string {
  return `${SITE_URL}${path}`
}

export function buildOrganizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'AI Orchestrator',
    url: SITE_URL,
    sameAs: [SITE_URL],
  }
}

export function buildSoftwareApplicationSchema(metadata: SeoMetadata) {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: metadata.title,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    description: metadata.description,
    url: buildCanonicalUrl(metadata.path),
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
  }
}

export function buildBreadcrumbSchema(path: string) {
  const routes = coreRoutes.filter((route) => route.href === '/' || route.href === path)
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: routes.map((route, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: route.label,
      item: buildCanonicalUrl(route.href),
    })),
}
}
