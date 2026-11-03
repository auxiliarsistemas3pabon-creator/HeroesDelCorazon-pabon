import { cn } from '../../lib/cn'

const variants = {
  primary: 'bg-primary text-white hover:bg-primary-dark focus-visible:ring-primary/50',
  secondary: 'bg-app-muted text-app border border-app hover:bg-primary/5 focus-visible:ring-primary/40',
  ghost: 'bg-transparent text-app hover:bg-app-muted focus-visible:ring-primary/30',
  danger: 'bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500/50',
}

const sizes = {
  xs: 'h-8 px-2 text-xs',
  sm: 'h-9 px-3 text-sm',
  md: 'h-11 px-4 text-sm',
  lg: 'h-12 px-6 text-sm',
}

// Botón del sistema (mismos estilos del software de equipos biomédicos).
export function Button({ variant = 'primary', size = 'md', loading, leftIcon, rightIcon, fullWidth, className, disabled, children, ...props }) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-(--bg)',
        'disabled:cursor-not-allowed disabled:opacity-60',
        variants[variant],
        sizes[size],
        fullWidth && 'w-full',
        className,
      )}
    >
      {loading ? <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  )
}
