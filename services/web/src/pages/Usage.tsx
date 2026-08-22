import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { AlertTriangle, Coins, Gauge, Settings2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { usageApi } from '@/api/usage'
import { PageHeader } from '@/components/PageHeader'
import { StatCard } from '@/components/StatCard'
import { BudgetEditorModal } from '@/components/BudgetEditorModal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import { useAuth } from '@/context/AuthContext'
import { cn, formatCurrency, formatDateTime, formatTokens } from '@/lib/utils'

export function Usage() {
  const { user } = useAuth()
  const [page, setPage] = useState(0)
  const [budgetOpen, setBudgetOpen] = useState(false)
  const pageSize = 20

  const summaryQuery = useQuery({ queryKey: ['usage-summary'], queryFn: usageApi.summary })
  const eventsQuery = useQuery({
    queryKey: ['usage-events', page],
    queryFn: () => usageApi.events(pageSize, page * pageSize),
  })

  const summary = summaryQuery.data
  const generation = summary?.by_kind.generation
  const embedding = summary?.by_kind.embedding
  const genCost = Number(generation?.cost_usd ?? 0)
  const embCost = Number(embedding?.cost_usd ?? 0)
  const totalKindCost = genCost + embCost || 1

  return (
    <div>
      <PageHeader
        title="Usage & billing"
        description="Track spend across generation and embedding calls."
        action={
          user?.role === 'admin' && (
            <Button variant="secondary" onClick={() => setBudgetOpen(true)}>
              <Settings2 className="h-4 w-4" />
              Set budget
            </Button>
          )
        }
      />

      <div className="px-6 pb-10 sm:px-8">
        {summaryQuery.isLoading && <PageSpinner />}

        {summary && (
          <>
            {summary.over_budget && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6 flex items-center gap-3 rounded-xl border border-danger-500/30 bg-danger-500/10 px-4 py-3 text-sm text-danger-500"
              >
                <AlertTriangle className="h-4 w-4 shrink-0" />
                Month-to-date spend has crossed the configured budget.
              </motion.div>
            )}

            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <StatCard
                label="Month-to-date cost"
                value={formatCurrency(summary.month_to_date_cost_usd)}
                icon={Coins}
                tone={summary.over_budget ? 'danger' : 'default'}
              />
              <StatCard
                label="Monthly budget"
                value={summary.monthly_budget_usd ? formatCurrency(summary.monthly_budget_usd) : 'No limit'}
                icon={Gauge}
                sub={
                  summary.budget_used_pct !== null && (
                    <div className="mt-1">
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/60">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.min(summary.budget_used_pct, 100)}%` }}
                          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                          className={cn('h-full rounded-full', summary.over_budget ? 'bg-danger-500' : 'bg-brand-500')}
                        />
                      </div>
                      <span className="mt-1 inline-block text-xs">{summary.budget_used_pct.toFixed(1)}% used</span>
                    </div>
                  )
                }
              />
              <StatCard
                label="Generation vs. embedding"
                value={
                  <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-border/60">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(genCost / totalKindCost) * 100}%` }}
                      transition={{ duration: 0.5 }}
                      className="h-full bg-brand-500"
                    />
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(embCost / totalKindCost) * 100}%` }}
                      transition={{ duration: 0.5 }}
                      className="h-full bg-info-500"
                    />
                  </div>
                }
                icon={Sparkles}
                sub={
                  <div className="flex gap-4">
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-brand-500" /> Generation {formatCurrency(genCost)}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-info-500" /> Embedding {formatCurrency(embCost)}
                    </span>
                  </div>
                }
              />
            </div>
          </>
        )}

        <div className="overflow-hidden rounded-2xl border border-border bg-surface">
          <div className="border-b border-border px-5 py-4">
            <h3 className="text-sm font-semibold text-text">Recent usage events</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-faint">
                  <th className="px-5 py-2.5 font-medium">When</th>
                  <th className="px-5 py-2.5 font-medium">Kind</th>
                  <th className="px-5 py-2.5 font-medium">Provider / model</th>
                  <th className="px-5 py-2.5 font-medium text-right">Tokens (in/out)</th>
                  <th className="px-5 py-2.5 font-medium text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {eventsQuery.data?.map((event) => (
                  <tr key={event.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-3 text-text-muted">{formatDateTime(event.created_at)}</td>
                    <td className="px-5 py-3">
                      <Badge tone={event.kind === 'generation' ? 'brand' : 'info'}>{event.kind}</Badge>
                    </td>
                    <td className="px-5 py-3 text-text-muted">
                      {event.provider} <span className="text-text-faint">· {event.model}</span>
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-text-muted">
                      {formatTokens(event.input_tokens)} / {formatTokens(event.output_tokens)}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-text">{formatCurrency(event.cost_usd)}</td>
                  </tr>
                ))}
                {eventsQuery.data?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-text-faint">
                      No usage recorded yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-border px-5 py-3">
            <Button variant="ghost" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span className="text-xs text-text-faint">Page {page + 1}</span>
            <Button
              variant="ghost"
              size="sm"
              disabled={(eventsQuery.data?.length ?? 0) < pageSize}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </div>

      <BudgetEditorModal open={budgetOpen} onClose={() => setBudgetOpen(false)} />
    </div>
  )
}
