import { clsx } from 'clsx'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'muted'
  size?: 'sm' | 'md'
  dot?: boolean
}

export function Badge({ children, variant = 'default', size = 'sm', dot }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full',
        {
          'px-2 py-0.5 text-xs gap-1': size === 'sm',
          'px-2.5 py-1 text-xs gap-1.5': size === 'md',
        },
        {
          'bg-surface-700 text-surface-300': variant === 'default',
          'bg-emerald-500/15 text-emerald-400': variant === 'success',
          'bg-amber-500/15 text-amber-400': variant === 'warning',
          'bg-red-500/15 text-red-400': variant === 'danger',
          'bg-blue-500/15 text-blue-400': variant === 'info',
          'bg-surface-800 text-surface-500': variant === 'muted',
        }
      )}
    >
      {dot && (
        <span
          className={clsx('w-1.5 h-1.5 rounded-full', {
            'bg-surface-400': variant === 'default',
            'bg-emerald-400': variant === 'success',
            'bg-amber-400': variant === 'warning',
            'bg-red-400': variant === 'danger',
            'bg-blue-400': variant === 'info',
            'bg-surface-500': variant === 'muted',
          })}
        />
      )}
      {children}
    </span>
  )
}
