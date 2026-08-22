import { ArrowUp } from 'lucide-react'
import { useRef, useState, type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'

interface ComposerProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

export function Composer({ onSend, disabled, placeholder = 'Ask a question…' }: ComposerProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
  }

  return (
    <div className="border-t border-border bg-bg p-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-border-strong bg-surface p-2 pl-4 shadow-[var(--shadow-soft)] focus-within:ring-2 focus-within:ring-ring dark:shadow-[var(--shadow-soft-dark)]">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
          placeholder={placeholder}
          className="max-h-48 flex-1 resize-none bg-transparent py-2.5 text-[15px] text-text placeholder:text-text-faint focus:outline-none disabled:opacity-60"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className={cn(
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors',
            value.trim() && !disabled
              ? 'bg-brand-600 text-white hover:bg-brand-700'
              : 'bg-border/60 text-text-faint',
          )}
        >
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-text-faint">
        Press Enter to send, Shift+Enter for a new line
      </p>
    </div>
  )
}
