import { apiFetch } from './client'
import type { UserCreate, UserOut, UserUpdate } from './types'

export const usersApi = {
  list: () => apiFetch<UserOut[]>('/users'),
  create: (body: UserCreate) => apiFetch<UserOut>('/users', { method: 'POST', body }),
  get: (id: string) => apiFetch<UserOut>(`/users/${id}`),
  update: (id: string, body: UserUpdate) =>
    apiFetch<UserOut>(`/users/${id}`, { method: 'PATCH', body }),
  delete: (id: string) => apiFetch<void>(`/users/${id}`, { method: 'DELETE' }),
}
