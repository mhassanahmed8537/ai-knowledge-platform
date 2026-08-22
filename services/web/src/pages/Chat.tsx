import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { chatApi, streamChatMessage } from '@/api/chat'
import { ApiError } from '@/api/client'
import type { ConversationOut } from '@/api/types'
import { Composer } from '@/components/chat/Composer'
import { ConversationList } from '@/components/chat/ConversationList'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { PageSpinner } from '@/components/ui/Spinner'
import { useToast } from '@/context/ToastContext'

export function Chat() {
  const { conversationId } = useParams<{ conversationId?: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const scrollAnchorRef = useRef<HTMLDivElement>(null)

  const [pendingUserText, setPendingUserText] = useState<string | null>(null)
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  const conversationsQuery = useQuery({
    queryKey: ['conversations'],
    queryFn: chatApi.listConversations,
  })

  const messagesQuery = useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => chatApi.listMessages(conversationId!),
    enabled: !!conversationId,
  })

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messagesQuery.data, streamingText, pendingUserText])

  const handleSend = async (message: string) => {
    let id = conversationId
    if (!id) {
      try {
        const conv = await chatApi.createConversation()
        id = conv.id
        queryClient.setQueryData<ConversationOut[]>(['conversations'], (old = []) => [conv, ...old])
        navigate(`/chat/${id}`, { replace: true })
      } catch {
        toast.push({ tone: 'error', title: 'Could not start a new conversation' })
        return
      }
    }

    setPendingUserText(message)
    setStreamingText('')
    setIsStreaming(true)

    try {
      await streamChatMessage(id, message, {
        onToken: (text) => setStreamingText((t) => t + text),
        onDone: async () => {
          await queryClient.invalidateQueries({ queryKey: ['messages', id] })
          setPendingUserText(null)
          setStreamingText('')
          setIsStreaming(false)
        },
      })
    } catch (err) {
      toast.push({
        tone: 'error',
        title: 'Message failed to send',
        description: err instanceof ApiError ? err.message : undefined,
      })
      setIsStreaming(false)
      setPendingUserText(null)
    }
  }

  const messages = messagesQuery.data ?? []
  const showEmptyState = !conversationId && !pendingUserText

  return (
    <div className="flex h-full">
      <ConversationList
        className="hidden w-72 shrink-0 sm:flex"
        conversations={conversationsQuery.data ?? []}
        isLoading={conversationsQuery.isLoading}
        onNew={() => navigate('/chat')}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {showEmptyState ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3 }}
              className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white"
            >
              <Sparkles className="h-7 w-7" />
            </motion.div>
            <div>
              <h2 className="text-xl font-semibold text-text">Ask anything about your documents</h2>
              <p className="mt-1.5 max-w-sm text-[15px] text-text-muted">
                Answers are grounded in your organization's uploaded documents, with inline citations.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6 sm:px-6">
              {messagesQuery.isLoading && <PageSpinner />}
              <AnimatePresence initial={false}>
                {messages.map((m) => (
                  <MessageBubble key={m.id} role={m.role} content={m.content} citations={m.citations} />
                ))}
                {pendingUserText && <MessageBubble key="pending-user" role="user" content={pendingUserText} />}
                {isStreaming && (
                  <MessageBubble key="streaming" role="assistant" content={streamingText} streaming />
                )}
              </AnimatePresence>
              <div ref={scrollAnchorRef} />
            </div>
          </div>
        )}

        <Composer onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  )
}
