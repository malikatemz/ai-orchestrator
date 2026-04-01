export function formatDate(value?: string | null): string {
  if (!value) {
    return 'No activity yet'
  }

  return new Date(value).toLocaleString()
}
