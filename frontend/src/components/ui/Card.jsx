import { cn } from '../../lib/cn'

const paddings = { none: '', sm: 'p-4', md: 'p-6', lg: 'p-8' }

export function Card({ children, padding = 'md', className, ...props }) {
  return (
    <div {...props} className={cn('rounded-xl border border-app bg-surface', paddings[padding], className)}>
      {children}
    </div>
  )
}

// Encabezado de tarjeta: título, subtítulo opcional y `action` (nodo, p. ej. un botón) alineado a la derecha.
export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h3 className="text-base font-semibold text-app">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-app-muted sm:text-sm">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}
