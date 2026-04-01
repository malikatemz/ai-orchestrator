import Head from 'next/head'

import { buildBreadcrumbSchema, buildCanonicalUrl, buildOrganizationSchema, buildSoftwareApplicationSchema, type SeoMetadata } from '../../lib/seo'

interface SeoHeadProps extends SeoMetadata {}

export function SeoHead({ title, description, path, keywords }: SeoHeadProps) {
  const canonical = buildCanonicalUrl(path)
  const organizationSchema = buildOrganizationSchema()
  const appSchema = buildSoftwareApplicationSchema({ title, description, path, keywords })
  const breadcrumbSchema = buildBreadcrumbSchema(path)

  return (
    <Head>
      <title>{title}</title>
      <meta name="description" content={description} />
      {keywords ? <meta name="keywords" content={keywords} /> : null}
      <meta name="robots" content="index,follow,max-image-preview:large" />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:type" content="website" />
      <meta property="og:url" content={canonical} />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <link rel="canonical" href={canonical} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(appSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }} />
    </Head>
  )
}
