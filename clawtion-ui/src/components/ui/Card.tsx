import { motion, type HTMLMotionProps } from 'framer-motion'
import { cn } from '@/lib/utils'

interface CardProps extends HTMLMotionProps<'div'> {
  children: React.ReactNode
  hover?: boolean
}

export function Card({ children, className, hover = false, ...props }: CardProps) {
  return (
    <motion.div
      whileHover={hover ? { scale: 1.005 } : undefined}
      className={cn(
        'rounded-lg border border-border bg-card p-5 shadow-sm',
        hover && 'cursor-pointer hover:shadow-md transition-shadow',
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  )
}
