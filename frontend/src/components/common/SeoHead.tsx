import Head from 'next/head'

import {
  buildBreadcrumbSchema,
  buildCanonicalUrl,
  buildOrganizationSchema,
  buildRobotsContent,
  buildSoftwareApplicationSchema,
  type FaqSchemaItem,
  type SeoMetadata,
  buildFaqSchema,
} from '../../lib/seo'

interface SeoHeadProps extends SeoMetadata {
  noindex?: boolean
  faqItems?: FaqSchemaItem[]
}

export function SeoHead({ title, description, path, keywords, noindex = false, faqItems = [] }: SeoHeadProps) {
  const canonical = buildCanonicalUrl(path)
  const organizationSchema = buildOrganizationSchema()
  const appSchema = buildSoftwareApplicationSchema({ title, description, path, keywords })
  const breadcrumbSchema = buildBreadcrumbSchema(path)
  const faqSchema = buildFaqSchema(faqItems)
  const structuredData = noindex ? [] : [organizationSchema, appSchema, breadcrumbSchema, faqSchema].filter(Boolean)

  return (
    <Head>
      <title>{title}</title>
      <meta name="description" content={description} />
      {keywords ? <meta name="keywords" content={keywords} /> : null}
      <meta name="robots" content={buildRobotsContent(noindex)} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:type" content="website" />
      {canonical ? <meta property="og:url" content={canonical} /> : null}
      <meta property="og:site_name" content="AI Orchestrator" />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      {canonical ? <link rel="canonical" href={canonical} /> : null}
      {structuredData.map((entry, index) => (
        <script key={index} type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(entry) }} />
      ))}
    </Head>
  )
}
