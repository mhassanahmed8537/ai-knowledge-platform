import { forwardRef, useId, type InputHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const fieldClasses =
  'w-full rounded-lg border border-border-strong bg-surface px-3.5 py-2.5 text-[15px] text-text placeholder:text-text-faint transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const generatedId = useId()
    const inputId = id ?? props.name ?? generatedId
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-text">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(fieldClasses, error && 'border-danger-500 focus:ring-danger-500', className)}
          aria-invalid={!!error}
          {...props}
        />
        {error && <p className="text-sm text-danger-500">{error}</p>}
        {hint && !error && <p className="text-sm text-text-faint">{hint}</p>}
      </div>
    )
  },
)
Input.displayName = 'Input'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const generatedId = useId()
    const inputId = id ?? props.name ?? generatedId
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-text">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={cn(fieldClasses, 'resize-none', error && 'border-danger-500 focus:ring-danger-500', className)}
          aria-invalid={!!error}
          {...props}
        />
        {error && <p className="text-sm text-danger-500">{error}</p>}
      </div>
    )
  },
)
Textarea.displayName = 'Textarea'
