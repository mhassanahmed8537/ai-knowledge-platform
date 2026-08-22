import { apiFetch } from './client'
import type { UsageEventOut, UsageSummaryOut } from './types'

export const usageApi = {
  summary: () => apiFetch<UsageSummaryOut>('/usage/summary'),
  events: (limit = 50, offset = 0) =>
    apiFetch<UsageEventOut[]>(`/usage/events?limit=${limit}&offset=${offset}`),
}
