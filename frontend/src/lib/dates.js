// Hoy como YYYY-MM-DD en la hora local (no en UTC): sirve de mínimo en los calendarios.
export const today = () => new Date().toLocaleDateString('sv-SE')

// "2026-10-31" -> "31 de octubre de 2026"
export function formatDay(iso) {
  if (!iso) return ''
  return new Date(`${iso}T00:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })
}
