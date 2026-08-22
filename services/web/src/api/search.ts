import { apiFetch } from './client'
import type { SearchHitOut, SearchRequest } from './types'

export const searchApi = {
  search: (body: SearchRequest) => apiFetch<SearchHitOut[]>('/search', { method: 'POST', body }),
}
