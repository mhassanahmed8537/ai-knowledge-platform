import { AnimatePresence, motion } from 'framer-motion'
import { Fragment, useState } from 'react'
import type { CitationOut } from '@/api/types'

const MARKER_RE = /\[(\d+)\]/g

/** Renders message text, turning `[n]` markers that resolve to a real
 * citation into interactive superscript chips; unresolved brackets (a
 * hallucinated marker the backend already dropped from `citations`) render
 * as plain text. */
export function CitationText({ content, citations }: { content: string; citations: CitationOut[] | null }) {
  const byMarker = new Map((citations ?? []).map((c) => [c.marker, c]))
  const parts: (string | { marker: number })[] = []
  let lastIndex = 0

  for (const match of content.matchAll(MARKER_RE)) {
    const marker = Number(match[1])
    if (!byMarker.has(marker)) continue
    if (match.index! > lastIndex) parts.push(content.slice(lastIndex, match.index))
    parts.push({ marker })
    lastIndex = match.index! + match[0].length
  }
  if (lastIndex < content.length) parts.push(content.slice(lastIndex))

  return (
    <span className="whitespace-pre-wrap">
      {parts.map((part, i) =>
        typeof part === 'string' ? (
          <Fragment key={i}>{part}</Fragment>
        ) : (
          <CitationChip key={i} citation={byMarker.get(part.marker)!} />
        ),
      )}
    </span>
  )
}

function CitationChip({ citation }: { citation: CitationOut }) {
  const [open, setOpen] = useState(false)

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="mx-0.5 inline-flex h-4 min-w-4 -translate-y-0.5 items-center justify-center rounded-full bg-brand-500/15 px-1 text-[10px] font-semibold text-brand-600 align-super hover:bg-brand-500/25 dark:text-brand-300"
      >
        {citation.marker}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.97 }}
            transition={{ duration: 0.12 }}
            className="absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 rounded-xl border border-border bg-surface-raised p-3 text-left shadow-[var(--shadow-soft)] dark:shadow-[var(--shadow-soft-dark)]"
          >
            <p className="mb-1 truncate text-xs font-semibold text-text">{citation.document_title}</p>
            <p className="line-clamp-4 text-xs leading-relaxed text-text-muted">{citation.snippet}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  )
}
