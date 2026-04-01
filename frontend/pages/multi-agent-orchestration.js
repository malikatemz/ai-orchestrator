import { MarketingPage } from '../src/components/marketing/MarketingPage'
import { marketingPages } from '../src/content/marketingPages'

export default function MultiAgentOrchestrationPage() {
  return <MarketingPage content={marketingPages.multiAgent} />
}
