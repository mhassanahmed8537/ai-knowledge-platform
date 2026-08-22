import { useQuery } from '@tanstack/react-query'
import { documentsApi } from '@/api/documents'
import type { DocumentOut } from '@/api/types'
import { Modal } from '@/components/ui/Modal'
import { PageSpinner } from '@/components/ui/Spinner'
import { formatTokens } from '@/lib/utils'

export function DocumentChunksModal({ document, onClose }: { document: DocumentOut | null; onClose: () => void }) {
  const chunksQuery = useQuery({
    queryKey: ['document-chunks', document?.id],
    queryFn: () => documentsApi.chunks(document!.id),
    enabled: !!document,
  })

  return (
    <Modal
      open={!!document}
      onClose={onClose}
      title={document?.title ?? ''}
      description={chunksQuery.data ? `${chunksQuery.data.length} chunks` : undefined}
      className="max-w-2xl"
    >
      <div className="max-h-[60vh] space-y-3 overflow-y-auto scrollbar-thin pr-1">
        {chunksQuery.isLoading && <PageSpinner />}
        {chunksQuery.data?.map((chunk) => (
          <div key={chunk.id} className="rounded-xl border border-border bg-bg p-3.5">
            <div className="mb-1.5 flex items-center justify-between text-xs text-text-faint">
              <span>Chunk {chunk.chunk_index + 1}</span>
              <span>{formatTokens(chunk.token_count)} tokens</span>
            </div>
            <p className="line-clamp-4 text-sm leading-relaxed text-text-muted">{chunk.content}</p>
          </div>
        ))}
        {chunksQuery.data?.length === 0 && (
          <p className="py-6 text-center text-sm text-text-faint">No chunks yet</p>
        )}
      </div>
    </Modal>
  )
}
