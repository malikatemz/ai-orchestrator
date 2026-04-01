import * as Sentry from '@sentry/nextjs'

interface CaptureErrorContext {
  area: 'frontend' | 'api'
  code?: string
  severity?: string
  requestId?: string
  retryable?: boolean
  details?: Record<string, unknown>
}

export function captureClientError(error: unknown, context: CaptureErrorContext): void {
  Sentry.withScope((scope) => {
    scope.setTag('area', context.area)
    if (context.code) scope.setTag('error_code', context.code)
    if (context.severity) scope.setTag('severity', context.severity)
    if (context.requestId) scope.setTag('request_id', context.requestId)
    if (typeof context.retryable === 'boolean') scope.setContext('retry', { retryable: context.retryable })
    if (context.details) scope.setContext('details', context.details)
    Sentry.captureException(error instanceof Error ? error : new Error(String(error)))
  })
}
