import { motion, type HTMLMotionProps } from 'framer-motion'
import { cn } from '@/lib/utils'

interface CardProps extends HTMLMotionProps<'div'> {
  children: React.ReactNode
  hover?: boolean
}

export function Card({ children, className, hover = false, ...props }: CardProps) {
  return (
    <motion.div
      whileHover={hover ? { y: -2, boxShadow: 'var(--shadow-card-hover)' } : undefined}
      className={cn(
        'rounded-lg border border-border-default bg-surface-card p-6 shadow-card',
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  )
}
