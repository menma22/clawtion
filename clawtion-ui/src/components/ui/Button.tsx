import { forwardRef } from 'react'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Spinner } from './Spinner'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: React.ReactNode
}

const variantClasses: Record<Variant, string> = {
  primary: 'bg-text text-app hover:bg-text/85 active:bg-text/75',
  secondary: 'bg-input text-text hover:bg-hover active:bg-active',
  danger: 'bg-danger text-white hover:bg-danger-hover active:bg-danger-hover',
  ghost: 'text-text-secondary hover:bg-hover active:bg-active',
}

const sizeClasses: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-[12px] rounded-md',
  md: 'h-8 px-3.5 text-[13px] rounded-md',
  lg: 'h-9 px-4 text-[14px] rounded-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, className, children, disabled, ...props }, ref) => (
    <motion.button
      ref={ref as any}
      whileTap={disabled || loading ? undefined : { scale: 0.98 }}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 font-medium tracking-tight transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent disabled:opacity-40 disabled:pointer-events-none cursor-pointer select-none',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner size="sm" className="text-current opacity-70" />}
      {children}
    </motion.button>
  )
)
Button.displayName = 'Button'
