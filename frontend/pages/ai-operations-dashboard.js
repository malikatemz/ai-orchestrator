import { MarketingPage } from '../src/components/marketing/MarketingPage'
import { marketingPages } from '../src/content/marketingPages'

export default function AiOperationsDashboardPage() {
  return <MarketingPage content={marketingPages.operations} />
}
