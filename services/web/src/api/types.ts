// Mirrors services/api/src/api/schemas.py and libs/core/core/enums.py exactly.
// Decimal fields serialize as strings over the wire (Pydantic JSON mode).

export type UserRole = 'admin' | 'member' | 'read_only'
export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'
export type MessageRole = 'user' | 'assistant'
export type UsageKind = 'generation' | 'embedding'
export type WebhookEvent = 'document.ready' | 'document.failed' | 'budget.alert'
export type SearchMode = 'hybrid' | 'vector' | 'lexical'

export interface SignupRequest {
  org_name: string
  email: string
  password: string
  full_name?: string | null
}

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface OrganizationOut {
  id: string
  name: string
  slug: string
  monthly_budget_usd: string | null
  created_at: string
}

export interface OrganizationUpdate {
  monthly_budget_usd: string | null
}

export interface UserOut {
  id: string
  org_id: string
  email: string
  full_name: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface UserCreate {
  email: string
  password: string
  full_name?: string | null
  role?: UserRole
}

export interface UserUpdate {
  full_name?: string | null
  role?: UserRole
  is_active?: boolean
}

export interface DocumentOut {
  id: string
  org_id: string
  title: string
  filename: string | null
  content_type: string | null
  status: DocumentStatus
  error: string | null
  created_at: string
}

export interface DocumentChunkOut {
  id: string
  chunk_index: number
  content: string
  token_count: number
  created_at: string
}

export interface SearchRequest {
  query: string
  mode?: SearchMode
  limit?: number | null
}

export interface SearchHitOut {
  chunk_id: string
  document_id: string
  document_title: string
  chunk_index: number
  content: string
  score: number
}

export interface ConversationCreate {
  title?: string | null
}

export interface ConversationOut {
  id: string
  org_id: string
  title: string | null
  created_at: string
}

export interface CitationOut {
  marker: number
  chunk_id: string
  document_id: string
  document_title: string
  snippet: string
}

export interface MessageOut {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  citations: CitationOut[] | null
  created_at: string
}

export interface ChatRequest {
  message: string
}

export interface ApiKeyCreate {
  name: string
  expires_in_days?: number | null
}

export interface ApiKeyOut {
  id: string
  name: string
  prefix: string
  last_used_at: string | null
  expires_at: string | null
  revoked_at: string | null
  created_at: string
}

export interface ApiKeyCreated extends ApiKeyOut {
  key: string
}

export interface UsageEventOut {
  id: string
  kind: UsageKind
  provider: string
  model: string
  input_tokens: number
  output_tokens: number
  cost_usd: string
  conversation_id: string | null
  document_id: string | null
  created_at: string
}

export interface UsageKindTotals {
  input_tokens: number
  output_tokens: number
  cost_usd: string
}

export interface UsageSummaryOut {
  month_to_date_cost_usd: string
  monthly_budget_usd: string | null
  budget_used_pct: number | null
  over_budget: boolean
  by_kind: Partial<Record<UsageKind, UsageKindTotals>>
}

export interface WebhookCreate {
  url: string
  event_types: WebhookEvent[]
}

export interface WebhookOut {
  id: string
  url: string
  event_types: WebhookEvent[]
  is_active: boolean
  created_at: string
}

export interface WebhookCreated extends WebhookOut {
  secret: string
}

export interface HealthOut {
  status: string
  database: string
  redis: string
  rls: string
}
