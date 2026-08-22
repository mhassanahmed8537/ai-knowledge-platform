import { apiFetch } from './client'
import type { WebhookCreate, WebhookCreated, WebhookOut } from './types'

export const webhooksApi = {
  list: () => apiFetch<WebhookOut[]>('/webhooks'),
  create: (body: WebhookCreate) =>
    apiFetch<WebhookCreated>('/webhooks', { method: 'POST', body }),
  delete: (id: string) => apiFetch<void>(`/webhooks/${id}`, { method: 'DELETE' }),
}
