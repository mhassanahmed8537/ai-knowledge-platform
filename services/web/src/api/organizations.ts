import { apiFetch } from './client'
import type { OrganizationOut, OrganizationUpdate } from './types'

export const organizationsApi = {
  me: () => apiFetch<OrganizationOut>('/organizations/me'),
  update: (body: OrganizationUpdate) =>
    apiFetch<OrganizationOut>('/organizations/me', { method: 'PATCH', body }),
}
