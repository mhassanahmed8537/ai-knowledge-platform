import { apiFetch, ApiError, BASE_URL } from './client'
import { tokenStore } from './tokenStore'
import type { CitationOut, ConversationCreate, ConversationOut, MessageOut } from './types'

export const chatApi = {
  listConversations: () => apiFetch<ConversationOut[]>('/conversations'),
  createConversation: (body: ConversationCreate = {}) =>
    apiFetch<ConversationOut>('/conversations', { method: 'POST', body }),
  listMessages: (conversationId: string) =>
    apiFetch<MessageOut[]>(`/conversations/${conversationId}/messages`),
}

export interface ChatStreamHandlers {
  onToken?: (text: string) => void
  onCitations?: (citations: CitationOut[]) => void
  onDone?: (length: number) => void
}

interface SseFrame {
  event: string
  data: string
}

function parseSseFrame(raw: string): SseFrame | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice('event: '.length)
    else if (line.startsWith('data: ')) dataLines.push(line.slice('data: '.length))
  }
  if (dataLines.length === 0) return null
  return { event, data: dataLines.join('\n') }
}

/**
 * Streams a chat reply via SSE. Uses a raw fetch + ReadableStream (not
 * EventSource) because the endpoint needs a POST body and an Authorization
 * header, neither of which EventSource supports.
 */
export async function streamChatMessage(
  conversationId: string,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const doRequest = async (): Promise<Response> => {
    const token = tokenStore.getAccessToken()
    return fetch(`${BASE_URL}/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message }),
      signal,
    })
  }

  let res = await doRequest()

  if (res.status === 401) {
    const refreshToken = tokenStore.getRefreshToken()
    if (refreshToken) {
      const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (refreshRes.ok) {
        const tokens = await refreshRes.json()
        tokenStore.setTokens(tokens.access_token, tokens.refresh_token)
        res = await doRequest()
      }
    }
  }

  if (!res.ok || !res.body) {
    let detail: unknown
    try {
      detail = (await res.json()).detail
    } catch {
      detail = undefined
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : res.statusText, detail)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const rawFrame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const frame = parseSseFrame(rawFrame)
      if (frame) dispatchFrame(frame, handlers)
      boundary = buffer.indexOf('\n\n')
    }
  }
}

function dispatchFrame(frame: SseFrame, handlers: ChatStreamHandlers): void {
  try {
    const payload = JSON.parse(frame.data)
    switch (frame.event) {
      case 'token':
        handlers.onToken?.(payload.text as string)
        break
      case 'citations':
        handlers.onCitations?.(payload.citations as CitationOut[])
        break
      case 'done':
        handlers.onDone?.(payload.length as number)
        break
    }
  } catch {
    // Malformed frame (shouldn't happen against this backend) -- drop it
    // rather than crash the stream.
  }
}
