import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { FileText, Trash2, UploadCloud } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { documentsApi } from '@/api/documents'
import { ApiError } from '@/api/client'
import type { DocumentOut } from '@/api/types'
import { PageHeader } from '@/components/PageHeader'
import { DocumentChunksModal } from '@/components/DocumentChunksModal'
import { DocumentStatusBadge } from '@/components/DocumentStatusBadge'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageSpinner } from '@/components/ui/Spinner'
import { useToast } from '@/context/ToastContext'
import { cn, formatDateTime } from '@/lib/utils'

export function Documents() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const [viewingDoc, setViewingDoc] = useState<DocumentOut | null>(null)
  const [deletingDoc, setDeletingDoc] = useState<DocumentOut | null>(null)

  const documentsQuery = useQuery({
    queryKey: ['documents'],
    queryFn: documentsApi.list,
    refetchInterval: (query) => {
      const docs = query.state.data ?? []
      return docs.some((d) => d.status === 'pending' || d.status === 'processing') ? 2000 : false
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => documentsApi.upload(file),
    onSuccess: (doc) => {
      queryClient.setQueryData<DocumentOut[]>(['documents'], (old = []) => [doc, ...old])
      toast.push({ tone: 'success', title: `Uploaded ${doc.filename}` })
    },
    onError: (err) => {
      toast.push({
        tone: 'error',
        title: 'Upload failed',
        description: err instanceof ApiError ? err.message : undefined,
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: (_void, id) => {
      queryClient.setQueryData<DocumentOut[]>(['documents'], (old = []) => old.filter((d) => d.id !== id))
    },
  })

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    for (const file of Array.from(files)) {
      if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        toast.push({ tone: 'error', title: `${file.name} isn't a PDF`, description: 'Only PDF uploads are supported.' })
        continue
      }
      uploadMutation.mutate(file)
    }
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
    handleFiles(e.dataTransfer.files)
  }

  const documents = documentsQuery.data ?? []

  return (
    <div>
      <PageHeader
        title="Documents"
        description="Upload PDFs to make them searchable and citable in chat."
        action={
          <Button onClick={() => fileInputRef.current?.click()} loading={uploadMutation.isPending}>
            <UploadCloud className="h-4 w-4" />
            Upload PDF
          </Button>
        }
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          handleFiles(e.target.files)
          e.target.value = ''
        }}
      />

      <div className="px-6 sm:px-8">
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragActive(true)
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            'mb-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors',
            dragActive ? 'border-brand-500 bg-brand-500/5' : 'border-border-strong hover:border-brand-400/60',
          )}
        >
          <UploadCloud className={cn('h-7 w-7', dragActive ? 'text-brand-500' : 'text-text-faint')} />
          <p className="text-sm font-medium text-text">Drag & drop a PDF, or click to browse</p>
          <p className="text-xs text-text-faint">Up to 25 MB per file</p>
        </div>

        {documentsQuery.isLoading && <PageSpinner />}

        {!documentsQuery.isLoading && documents.length === 0 && (
          <EmptyState icon={FileText} title="No documents yet" description="Upload your first PDF to get started." />
        )}

        <div className="space-y-2 pb-8">
          <AnimatePresence initial={false}>
            {documents.map((doc) => (
              <motion.div
                key={doc.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.2 }}
                className="flex items-center gap-4 rounded-xl border border-border bg-surface p-4"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-500/10 text-brand-500">
                  <FileText className="h-5 w-5" />
                </div>
                <button
                  onClick={() => doc.status === 'ready' && setViewingDoc(doc)}
                  className="min-w-0 flex-1 text-left"
                  disabled={doc.status !== 'ready'}
                >
                  <p className="truncate text-sm font-medium text-text">{doc.title}</p>
                  <p className="truncate text-xs text-text-faint">
                    {formatDateTime(doc.created_at)}
                    {doc.status === 'failed' && doc.error ? ` · ${doc.error}` : ''}
                  </p>
                </button>
                <DocumentStatusBadge status={doc.status} />
                <button
                  onClick={() => setDeletingDoc(doc)}
                  className="rounded-lg p-2 text-text-faint transition-colors hover:bg-danger-500/10 hover:text-danger-500"
                  aria-label="Delete document"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      <DocumentChunksModal document={viewingDoc} onClose={() => setViewingDoc(null)} />
      <ConfirmDialog
        open={!!deletingDoc}
        onClose={() => setDeletingDoc(null)}
        title={`Delete "${deletingDoc?.title}"?`}
        description="This permanently removes the document and its indexed chunks."
        confirmLabel="Delete"
        onConfirm={async () => {
          if (deletingDoc) await deleteMutation.mutateAsync(deletingDoc.id)
        }}
      />
    </div>
  )
}
