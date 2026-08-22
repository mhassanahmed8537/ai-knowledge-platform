import { useMutation } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { FileSearch, SearchIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { searchApi } from '@/api/search'
import type { SearchHitOut, SearchMode } from '@/api/types'
import { PageHeader } from '@/components/PageHeader'
import { Input } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageSpinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

const MODES: { value: SearchMode; label: string }[] = [
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'vector', label: 'Semantic' },
  { value: 'lexical', label: 'Keyword' },
]

export function Search() {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('hybrid')
  const [hasSearched, setHasSearched] = useState(false)

  const searchMutation = useMutation({
    mutationFn: (vars: { query: string; mode: SearchMode }) =>
      searchApi.search({ query: vars.query, mode: vars.mode }),
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setHasSearched(true)
    searchMutation.mutate({ query: query.trim(), mode })
  }

  const results = searchMutation.data ?? []
  const maxScore = Math.max(...results.map((r) => r.score), 0.0001)

  return (
    <div>
      <PageHeader title="Search" description="Search directly across your indexed document chunks." />

      <div className="px-6 sm:px-8">
        <form onSubmit={handleSubmit} className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="flex-1">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search your documents…"
              autoFocus
            />
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-border-strong bg-surface p-1">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => setMode(m.value)}
                className={cn(
                  'relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  mode === m.value ? 'text-white' : 'text-text-muted hover:text-text',
                )}
              >
                {mode === m.value && (
                  <motion.div
                    layoutId="search-mode-active"
                    className="absolute inset-0 rounded-md bg-brand-600"
                    transition={{ duration: 0.2 }}
                  />
                )}
                <span className="relative">{m.label}</span>
              </button>
            ))}
          </div>
        </form>

        {searchMutation.isPending && <PageSpinner />}

        {!searchMutation.isPending && hasSearched && results.length === 0 && (
          <EmptyState icon={SearchIcon} title="No results" description="Try a different query or search mode." />
        )}

        {!hasSearched && (
          <EmptyState
            icon={FileSearch}
            title="Search across your knowledge base"
            description="Results are ranked using reciprocal rank fusion across lexical and vector arms."
          />
        )}

        <div className="space-y-2 pb-8">
          <AnimatePresence>
            {results.map((hit: SearchHitOut, i) => (
              <motion.div
                key={hit.chunk_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: Math.min(i, 8) * 0.03 }}
                className="rounded-xl border border-border bg-surface p-4"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="truncate text-sm font-medium text-text">{hit.document_title}</p>
                  <span className="shrink-0 text-xs text-text-faint">chunk {hit.chunk_index + 1}</span>
                </div>
                <p className="mb-3 line-clamp-3 text-sm leading-relaxed text-text-muted">{hit.content}</p>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border/60">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(hit.score / maxScore) * 100}%` }}
                      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                      className="h-full rounded-full bg-brand-500"
                    />
                  </div>
                  <span className="text-xs tabular-nums text-text-faint">{hit.score.toFixed(3)}</span>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
