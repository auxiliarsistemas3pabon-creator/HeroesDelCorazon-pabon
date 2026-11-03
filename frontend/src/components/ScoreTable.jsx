import { cn } from '../lib/cn'
import { ratingScale } from '../lib/ratingScales'


// Tabla de calificación: categoría (agrupada) | criterio | 1 2 3 4 5. La nota elegida se marca con una X.
// Solo en la vista de revisión del jefe: la última columna muestra el promedio de cada categoría. Al colaborador no se le muestra mientras califica.
// Sin `onChange` la tabla es de solo lectura (pantalla de revisión del jefe).
//
// Con `editor` la misma tabla sirve para armar la evaluación (pantalla "Configurar evaluación"): llega vacía,
// sin notas ni promedio, y el jefe escribe en las celdas de categoría y criterio.
//   editor = { renderCategory(category), renderCriterion(criterion, category), renderActions(criterion, category), renderAdd(category) }
//   renderAdd devuelve las celdas de la fila final: criterio | (una celda que abarca las 5 columnas de notas) | acciones
function categoryAverage(category, scores) {
  const given = category.criteria.map((c) => scores[c.code]).filter((n) => n !== undefined && n > 0)
  if (given.length === 0) return '—'
  return (given.reduce((sum, n) => sum + n, 0) / given.length).toFixed(1)
}

// Clases base de celdas; HEAD es la variante de encabezado.
const CELL = 'border border-app px-2.5 py-2 text-left align-middle'
const HEAD = `${CELL} bg-app-muted font-semibold`

// Props: `categories` = [{ code, name, criteria: [{ code, name }] }]; `scores` = { [codigoCriterio]: nota };
// `onChange(codigoCriterio, nota)`; `name` evita colisiones de radios si hay varias tablas en pantalla;
// `ratingType` es una clave de RATING_SCALES (escalas descriptivas muestran la etiqueta en vez del número).
export function ScoreTable({ categories, scores = {}, onChange, name = 'scores', editor, ratingType = 'quantitative' }) {
  const options = ratingScale(ratingType).options
  const readOnly = !onChange
  const showAverage = readOnly && !editor
  // Con escalas cualitativas las columnas son más anchas porque el encabezado es texto, no un número.
  const showDescriptions = !ratingType.startsWith('quantitative')

  return (
    <div className="mt-3 overflow-x-auto">
      <table className={cn('w-full border-collapse text-sm', editor ? 'min-w-225' : 'min-w-160')}>
        <thead>
          <tr>
            <th className={cn(HEAD, 'min-w-40')}>Categoría</th>
            <th className={cn(HEAD, 'min-w-40')}>Criterio</th>
            {options.map(({ score, label }) => (
              <th key={score} className={cn(showDescriptions ? 'min-w-24 text-center' : 'w-12 text-center', 'whitespace-normal align-middle', HEAD)}>
                <span className="block whitespace-normal break-words font-normal leading-snug">{showDescriptions ? label : score}</span>
              </th>
            ))}
            {showAverage && <th className={cn(HEAD, 'w-36 min-w-36 text-center')}>Promedio por categoría</th>}
            {editor && <th className={cn(HEAD, 'w-32')}>Acciones</th>}
          </tr>
        </thead>
        <tbody>
          {categories.map((category) => {
            // En el editor, cada categoría termina con una fila para agregar otra pregunta.
            const rows = [
              ...category.criteria.map((criterion) => ({ key: criterion.code, criterion })),
              ...(editor ? [{ key: `${category.code}-add`, add: true }] : []),
            ]

            return rows.map((row, index) => {
              // Una línea más marcada separa cada categoría de la siguiente.
              const cell = (...extra) => cn(CELL, index === 0 && 'border-t-2 border-t-gray-400', row.add && 'bg-app-muted', ...extra)

              return (
                <tr key={row.key}>
                  {index === 0 && (
                    <th rowSpan={rows.length} scope="rowgroup" className={cn(CELL, 'w-37.5 min-w-40 whitespace-normal break-words border-t-2 border-t-gray-400 bg-primary/5 font-semibold text-primary')}>
                      {editor ? editor.renderCategory(category) : category.name}
                    </th>
                  )}

                  {row.add ? (
                    editor.renderAdd(category)
                  ) : (
                    <>
                      <td className={cell('min-w-40 whitespace-normal break-words')}>{editor ? editor.renderCriterion(row.criterion, category) : row.criterion.name}</td>
                      {options.map(({ score, label }) => {
                        const checked = scores[row.criterion.code] === score
                        return (
                          <td key={score} className={cell(showDescriptions ? 'min-w-24 p-1 text-center' : 'w-12 p-1 text-center')}>
                            <label
                              className={cn(
                                'relative grid h-9 w-full min-w-9 place-items-center rounded-md text-base font-bold text-primary',
                                'has-focus-visible:outline-2 has-focus-visible:-outline-offset-2 has-focus-visible:outline-primary',
                                checked && 'bg-primary/10',
                                readOnly ? 'cursor-default' : 'cursor-pointer hover:bg-primary/10',
                              )}
                              title={showDescriptions ? label : `Nota ${score}`}
                            >
                              <input
                                type="radio"
                                className="absolute inset-0 m-0 cursor-[inherit] opacity-0"
                                name={`${name}-${row.criterion.code}`}
                                checked={checked}
                                disabled={readOnly}
                                onChange={() => onChange(row.criterion.code, score)}
                                aria-label={`${row.criterion.name} — ${showDescriptions ? label : score}`}
                              />
                              <span>{checked ? 'X' : ''}</span>
                            </label>
                          </td>
                        )
                      })}
                      {editor && <td className={cell('w-32 whitespace-normal break-words')}>{editor.renderActions(row.criterion, category)}</td>}
                    </>
                  )}

                  {showAverage && index === 0 && (
                    <td rowSpan={rows.length} className={cn(CELL, 'border-t-2 border-t-gray-400 bg-primary/5 text-center text-lg font-bold text-primary')}>
                      {categoryAverage(category, scores)}
                    </td>
                  )}
                </tr>
              )
            })
          })}
        </tbody>
      </table>
    </div>
  )
}
