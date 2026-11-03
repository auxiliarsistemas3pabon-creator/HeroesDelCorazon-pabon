import { cn } from '../../lib/cn'

// `tone` selecciona el color semántico; los tonos con color llevan variante para modo oscuro.
const tones = {
  neutral: 'bg-app-muted text-app-muted border border-app',
  success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400',
  warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400',
  danger: 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400',
  info: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400',
  primary: 'bg-primary/10 text-primary',
}

export function Badge({ children, tone = 'neutral', className }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium', tones[tone], className)}>
      {children}
    </span>
  )
}
