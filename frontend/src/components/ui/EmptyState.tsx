import { Loader2 } from 'lucide-react'

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: React.ElementType
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      <div className="w-14 h-14 rounded-2xl bg-surface-800 flex items-center justify-center mb-4">
        <Icon className="w-7 h-7 text-surface-500" />
      </div>
      <h3 className="text-lg font-semibold text-surface-200 mb-1">{title}</h3>
      <p className="text-sm text-surface-400 max-w-sm mb-6">{description}</p>
      {action}
    </div>
  )
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center py-24">
      <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
    </div>
  )
}

export function PageError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center mb-4">
        <span className="text-2xl">⚠</span>
      </div>
      <h3 className="text-lg font-semibold text-surface-200 mb-1">Something went wrong</h3>
      <p className="text-sm text-surface-400 mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-sm font-medium text-primary-400 hover:text-primary-300 cursor-pointer"
        >
          Try again
        </button>
      )}
    </div>
  )
}
