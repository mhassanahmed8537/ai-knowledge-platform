import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import type { CitationOut, MessageRole } from '@/api/types'
import { cn } from '@/lib/utils'
import { CitationText } from './CitationText'

interface MessageBubbleProps {
  role: MessageRole
  content: string
  citations?: CitationOut[] | null
  streaming?: boolean
}

export function MessageBubble({ role, content, citations, streaming }: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className={cn('flex gap-3', isUser ? 'justify-end' : 'justify-start')}
    >
      {!isUser && (
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
      )}
      <div
        className={cn(
          'max-w-[min(640px,80%)] rounded-2xl px-4 py-3 text-[15px] leading-relaxed',
          isUser
            ? 'rounded-tr-sm bg-brand-600 text-white'
            : 'rounded-tl-sm border border-border bg-surface text-text',
        )}
      >
        {content || streaming ? (
          <CitationText content={content} citations={citations ?? null} />
        ) : null}
        {streaming && (
          <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-current opacity-70" />
        )}
      </div>
    </motion.div>
  )
}
