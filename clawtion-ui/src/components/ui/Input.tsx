import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  icon?: React.ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, className, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={inputId} className="text-[12px] font-medium text-text-secondary">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary">
              {icon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'h-9 w-full rounded-md border border-border bg-input px-2.5 text-[13px] text-text placeholder:text-text-tertiary',
              'focus:border-accent/40 focus:outline-none focus:ring-2 focus:ring-accent/10 transition-all',
              icon && 'pl-8',
              error && 'border-danger focus:border-danger focus:ring-danger/10',
              className,
            )}
            {...props}
          />
        </div>
        {error && <p className="text-[11px] text-danger">{error}</p>}
      </div>
    )
  },
)
Input.displayName = 'Input'
