import React from 'react'
import type { MarketingPageContent } from '../../content/marketingPages'
import { MarketingLayout } from './MarketingLayout'

interface MarketingPageProps {
  content: MarketingPageContent
}

export function MarketingPage({ content }: MarketingPageProps) {
  return (
    <MarketingLayout
      title={content.title}
      description={content.description}
      path={content.path}
      eyebrow={content.eyebrow}
      heading={content.heading}
      intro={content.intro}
    >
      {content.body}
    </MarketingLayout>
  )
}
