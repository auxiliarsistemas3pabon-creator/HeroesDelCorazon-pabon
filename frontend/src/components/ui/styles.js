// Clases de Tailwind compartidas por los campos de formulario y las alertas (las mismas del software de equipos biomédicos).
export const FIELD =
  'w-full rounded-lg border border-app bg-surface px-3 py-2.5 text-sm text-app outline-none transition placeholder:text-app-muted focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60'
export const LABEL = 'flex flex-col gap-1.5 text-sm font-medium text-app'
export const ALERT_ERROR =
  'rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300'
export const ALERT_OK =
  'rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300'
export const PAGE_TITLE = 'text-2xl font-bold text-app'
export const PAGE_SUBTITLE = 'mt-1 text-sm text-app-muted'
export const TH = 'whitespace-nowrap px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-app-muted'
// Cuadro de texto dentro de una celda de tabla editable (Configurar evaluación): borde visible siempre y crece con el texto.
export const CELL_INPUT =
  'block w-full resize-none overflow-hidden rounded-md border border-gray-300 bg-surface px-2 py-2 text-sm leading-snug text-app outline-none transition hover:border-gray-400 focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-60'
