import { apiFetch, apiUpload } from './client'
import type { DocumentChunkOut, DocumentOut } from './types'

export const documentsApi = {
  list: () => apiFetch<DocumentOut[]>('/documents'),
  get: (id: string) => apiFetch<DocumentOut>(`/documents/${id}`),
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiUpload<DocumentOut>('/documents/upload', form)
  },
  chunks: (id: string) => apiFetch<DocumentChunkOut[]>(`/documents/${id}/chunks`),
  rename: (id: string, title: string) =>
    apiFetch<DocumentOut>(`/documents/${id}`, { method: 'PATCH', body: { title } }),
  delete: (id: string) => apiFetch<void>(`/documents/${id}`, { method: 'DELETE' }),
}
