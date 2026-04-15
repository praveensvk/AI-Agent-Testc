import { clsx } from 'clsx'

interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  onClick?: () => void
}

export function Card({ children, className, hover, onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        'rounded-xl border border-surface-800 bg-surface-900',
        hover && 'cursor-pointer hover:border-surface-700 hover:bg-surface-800/70 transition-all duration-150',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps {
  children: React.ReactNode
  className?: string
}

export function CardHeader({ children, className }: CardHeaderProps) {
  return (
    <div className={clsx('px-5 py-4 border-b border-surface-800', className)}>
      {children}
    </div>
  )
}

export function CardContent({ children, className }: CardHeaderProps) {
  return <div className={clsx('px-5 py-4', className)}>{children}</div>
}
