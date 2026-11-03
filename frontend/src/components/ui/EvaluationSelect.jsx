import { AutocompleteSelect } from './AutocompleteSelect'
import { LABEL } from './styles'
import { formatDay } from '../../lib/dates'

const nameKey = (name) => name.normalize('NFD').replace(/[̀-ͯ]/g, '').trim().replace(/\s+/g, ' ').toLocaleLowerCase()

// Las programaciones comparten nombre (cada una es copia de otra): el primer selector lista cada nombre una vez; al
// elegirlo se selecciona su programación más reciente y, si hay varias, un segundo selector lista las de ese nombre por fecha.
// `value` es el id (string) de la evaluación elegida; `onChange` recibe el id elegido.
// Con `showDate` el primer selector también muestra la fecha de cierre junto al nombre (la de la programación elegida).
export function EvaluationSelect({ evaluations, value, onChange, placeholder = 'Selecciona evaluación', showDate = false }) {
  const groups = []
  for (const evaluation of [...evaluations].sort((a, b) => b.id - a.id)) {
    const key = nameKey(evaluation.name)
    const group = groups.find((item) => item.key === key)
    if (group) group.items.push(evaluation)
    else groups.push({ key, name: evaluation.name.trim(), items: [evaluation] })
  }

  const current = evaluations.find((item) => String(item.id) === value)
  const group = current ? groups.find((item) => item.key === nameKey(current.name)) : null
  const versions = group?.items ?? []
  const closing = (item) => `Cierra ${item.closes_on ? formatDay(item.closes_on) : 'Sin fecha'}`

  return (
    <>
      <label className={`${LABEL} w-full sm:w-auto sm:min-w-56`}>
        Evaluación
        <AutocompleteSelect
          value={group?.key ?? ''}
          onChange={(key) => {
            const latest = groups.find((item) => item.key === key)?.items[0]
            onChange(latest ? String(latest.id) : '')
          }}
          placeholder={placeholder}
          options={groups.map((item) => ({
            value: item.key,
            label: showDate ? `${item.name} (${closing(item === group ? current : item.items[0])})` : item.name,
          }))}
        />
      </label>
      {versions.length > 1 && (
        <label className={`${LABEL} w-full sm:w-auto sm:min-w-56`}>
          {versions[0].name.trim()}: elige una
          <AutocompleteSelect
            value={value}
            onChange={onChange}
            options={versions.map((item) => ({
              value: String(item.id),
              label: `${item.name.trim()} (${closing(item)})`,
            }))}
          />
        </label>
      )}
    </>
  )
}
