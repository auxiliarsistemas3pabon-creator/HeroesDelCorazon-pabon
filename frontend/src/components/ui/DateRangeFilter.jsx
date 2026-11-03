import { FIELD, LABEL } from './styles'

// Filtro Desde/Hasta por fecha de realización. Se aplica solo al cambiar un valor (sin botón); `from`/`to` son YYYY-MM-DD.
// Si el rango queda invertido, cada campo limita al otro con min/max.
export function DateRangeFilter({ from, to, onChange }) {
  return (
    <>
      <label className={`${LABEL} min-w-44`}>
        Desde
        <input
          type="date"
          className={FIELD}
          value={from}
          max={to || undefined}
          onChange={(e) => onChange({ from: e.target.value, to })}
        />
      </label>
      <label className={`${LABEL} min-w-44`}>
        Hasta
        <input
          type="date"
          className={FIELD}
          value={to}
          min={from || undefined}
          onChange={(e) => onChange({ from, to: e.target.value })}
        />
      </label>
    </>
  )
}
