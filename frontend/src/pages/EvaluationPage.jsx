import { useEffect, useState } from 'react'
import { ScoreTable } from '../components/ScoreTable'
import { ratingScale } from '../lib/ratingScales'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ALERT_ERROR, ALERT_OK, PAGE_SUBTITLE, PAGE_TITLE } from '../components/ui/styles'
import { api, errorMessage } from '../lib/api'
import { cn } from '../lib/cn'
import { formatDay } from '../lib/dates'

// Formulario de UNA evaluación: el colaborador elige los compañeros de su área que el jefe habilita cada mes y los califica.
function EvaluationForm({ evaluation, onBack }) {
  // Todos los endpoints se acotan por evaluación con este querystring.
  const q = `?evaluation=${evaluation.id}`
  const [quota, setQuota] = useState(null)
  const [categories, setCategories] = useState([])
  const [people, setPeople] = useState([])
  const [selected, setSelected] = useState([])
  const [scores, setScores] = useState({})
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [peoplePage, setPeoplePage] = useState(1)

  // Carga en paralelo: criterios del formulario, colaboradores (el backend ya limita a los visibles para el usuario)
  // y cupo mensual. Si cualquiera falla se muestra un solo error.
  useEffect(() => {
    Promise.all([api(`/questions/form/${q}`), api('/users/collaborators/'), api(`/questions/quota/${q}`)])
      .then(([form, users, monthly]) => {
        setCategories(form)
        setPeople(users)
        setQuota(monthly)
      })
      .catch((e) => setError(errorMessage(e)))
  }, [q])

  // Cupo mensual: lo define el jefe; los ya calificados este mes no se pueden repetir.
  const max = quota ? Math.max(0, quota.limit - quota.used) : 0
  // Alcance de la evaluación: `areas === null` significa todas las áreas. El jefe no designa personas: en modo manual
  // se listan todas las de su área (el backend ya filtra por área) y en modo aleatorio se usan las asignadas.
  const scopedPeople = people.filter((person) => evaluation.areas === null || evaluation.areas.includes(person.area))
  const available = quota ? scopedPeople.filter((p) => !quota.personal.includes(p.id)) : []
  // Selección aleatoria: el sistema le asigna a este colaborador sus personas (quota.assigned) y no puede cambiarlas.
  // Selección manual: el colaborador elige entre las personas de su área.
  const fixedPeople = evaluation.random_selection && quota?.assigned
    ? available.filter((p) => quota.assigned.includes(p.id)).slice(0, max)
    : null
  // Selección manual: 5 personas por página; lo marcado se conserva al cambiar de página.
  const PEOPLE_PER_PAGE = 5
  const peopleTotalPages = Math.max(1, Math.ceil(available.length / PEOPLE_PER_PAGE))
  const currentPeoplePage = Math.min(peoplePage, peopleTotalPages)
  const visiblePeople = fixedPeople ?? available.slice((currentPeoplePage - 1) * PEOPLE_PER_PAGE, currentPeoplePage * PEOPLE_PER_PAGE)
  const effectiveSelected = fixedPeople ? fixedPeople.map((p) => p.id) : selected
  const pending = quota ? Math.max(0, max - effectiveSelected.length) : 0

  // Las respuestas se guardan planas por persona+criterio (`personId:code`) porque las categorías solo agrupan visualmente.
  const criteria = categories.flatMap((c) => c.criteria)
  const key = (personId, code) => `${personId}:${code}`
  const isComplete = (personId) => criteria.every((c) => scores[key(personId, c.code)])
  // Enviar solo se habilita cuando se eligió TODO el cupo restante y cada persona tiene todos los criterios calificados.
  const ready = max > 0 && (fixedPeople ? effectiveSelected.length > 0 : effectiveSelected.length === max) && effectiveSelected.every(isComplete)
  const full = max > 0 && effectiveSelected.length >= max // ya elegiste todos: el resto queda bloqueado

  function toggle(personId) {
    setSaved(false)
    setSelected((current) => {
      if (current.includes(personId)) return current.filter((id) => id !== personId)
      return current.length < max ? [...current, personId] : current
    })
  }

  // Envía una evaluación por persona (un POST cada una, secuencial). Si una falla, las anteriores ya quedaron guardadas,
  // por eso en ambos casos se vuelve a pedir el cupo al backend para reflejar lo realmente guardado.
  async function onSubmit(e) {
    e.preventDefault()
    setError(null)
    setSaved(false)
    setSaving(true)
    try {
      for (const personId of effectiveSelected) {
        await api('/questions/', {
          method: 'POST',
          body: {
            evaluation: evaluation.id,
            personal: personId,
            answers: criteria.map((c) => ({ criterion: c.code, score: Number(scores[key(personId, c.code)]) })),
          },
        })
      }
      setSaved(true)
      setSelected([])
      setScores({})
      setQuota(await api(`/questions/quota/${q}`))
    } catch (err) {
      setError(errorMessage(err, 'No se pudo guardar la evaluación'))
      setQuota(await api(`/questions/quota/${q}`).catch(() => quota))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {onBack && <Button type="button" variant="secondary" size="sm" onClick={onBack}>← Otras evaluaciones</Button>}
      <div>
        <h1 className={PAGE_TITLE}>{evaluation.name}</h1>
        {evaluation.closes_on && <p className={PAGE_SUBTITLE}>Puedes responder hasta el {formatDay(evaluation.closes_on)}.</p>}
      </div>
      <p className="text-sm text-app-muted">
        {`${fixedPeople ? 'Evalúa a las personas que el sistema te asignó y marca' : `Elige ${quota ? max : 0} personas de tu área y marca`} con una X la opción que mejor describa cada criterio. ${ratingScale(evaluation.rating_type).description}`}
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        {error && <div role="alert" className={ALERT_ERROR}>{error}</div>}
        {saved && <div className={ALERT_OK}>Evaluaciones enviadas al jefe de área.</div>}

        <Card>
          <h3 className="text-base font-semibold text-app">Usuarios a evaluar ({effectiveSelected.length} {fixedPeople ? 'asignados' : 'seleccionados'})</h3>
          {quota && max > 0 && <p className="mt-1 text-sm text-app-muted">Pendientes por evaluar este mes: {pending} de {quota.limit}. Ya evaluaste {quota.used}.</p>}
          {quota && max === 0 && <div className={`mt-2 ${ALERT_OK}`}>Evaluación realizada con éxito.</div>}
          {quota && max > 0 && available.length === 0 && <p className="mt-2 text-sm text-app-muted">No hay usuarios disponibles de tu área para evaluar.</p>}
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {(max > 0 ? visiblePeople : []).map((p) => {
              const checked = effectiveSelected.includes(p.id)
              const locked = !fixedPeople && full && !checked
              return (
                <label
                  key={p.id}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition',
                    checked ? 'border-primary bg-primary/5 font-medium text-primary' : 'border-app bg-surface text-app',
                    locked ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:bg-app-muted',
                  )}
                >
                  <input
                    className="accent-primary"
                    type="checkbox"
                    checked={checked}
                    disabled={locked || Boolean(fixedPeople)}
                    onChange={() => toggle(p.id)}
                  />
                  {p.first_name} {p.last_name}
                </label>
              )
            })}
          </div>
          {max > 0 && !fixedPeople && peopleTotalPages > 1 && (
            <div className="mt-3 flex items-center justify-between gap-2">
              <Button type="button" variant="secondary" size="sm" disabled={currentPeoplePage === 1} onClick={() => setPeoplePage(currentPeoplePage - 1)}>Anterior</Button>
              <span className="text-xs text-app-muted">Página {currentPeoplePage} de {peopleTotalPages}</span>
              <Button type="button" variant="secondary" size="sm" disabled={currentPeoplePage === peopleTotalPages} onClick={() => setPeoplePage(currentPeoplePage + 1)}>Siguiente</Button>
            </div>
          )}
          {full && !fixedPeople && <p className="mt-2.5 text-xs text-app-muted">Ya elegiste a los {max} compañeros. Desmarca uno si quieres cambiarlo.</p>}
        </Card>

        {effectiveSelected.map((personId) => {
          const person = people.find((p) => p.id === personId)
          return (
            <Card key={personId}>
              <h3 className="text-base font-semibold text-app">{person.first_name} {person.last_name}</h3>
              <ScoreTable
                name={`person-${personId}`}
                categories={categories}
                ratingType={evaluation.rating_type}
                scores={Object.fromEntries(criteria.map((c) => [c.code, scores[key(personId, c.code)]]))}
                onChange={(code, n) => setScores((s) => ({ ...s, [key(personId, code)]: n }))}
              />
            </Card>
          )
        })}

        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-app-muted">Seleccionados {effectiveSelected.length} · pendientes por evaluar {pending}</span>
          <Button type="submit" disabled={saving || !ready}>
            {saving ? 'Enviando...' : 'Enviar al jefe'}
          </Button>
        </div>
      </form>
    </div>
  )
}

// Tarjetas por página en el selector de evaluaciones.
const PAGE_SIZE = 6

// El colaborador solo responde las evaluaciones que el jefe dejó abiertas: si hay varias, elige cuál.
export function EvaluationPage() {
  const [evaluations, setEvaluations] = useState(null)
  const [chosen, setChosen] = useState(null)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    api('/questions/evaluations/')
      .then(setEvaluations)
      .catch((e) => setError(errorMessage(e)))
  }, [])

  if (error) return <div role="alert" className={ALERT_ERROR}>{error}</div>
  if (!evaluations) return <p className="text-sm text-app-muted">Cargando...</p>

  if (evaluations.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className={PAGE_TITLE}>ESCALA DE VALORACIÓN</h1>
        <Card className="text-app-muted">No hay evaluaciones abiertas en este momento.</Card>
      </div>
    )
  }

  // Con una sola evaluación abierta se salta el selector; `onBack` solo se ofrece si hay más de una.
  // El `key` reinicia todo el estado del formulario al cambiar de evaluación.
  const current = evaluations.length === 1 ? evaluations[0] : evaluations.find((e) => e.id === chosen)
  if (current) {
    return <EvaluationForm key={current.id} evaluation={current} onBack={evaluations.length > 1 ? () => setChosen(null) : null} />
  }

  // Las completadas (sin cupo restante) van al final; el orden del resto se conserva.
  // `remaining` es el cupo mensual restante calculado por el backend.
  const sorted = [...evaluations].sort((a, b) => (a.remaining === 0) - (b.remaining === 0))
  const pageCount = Math.ceil(sorted.length / PAGE_SIZE)
  const visible = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <div className="space-y-6">
      <div>
        <h1 className={PAGE_TITLE}>ESCALA DE VALORACIÓN</h1>
        <p className={PAGE_SUBTITLE}>Hay varias evaluaciones abiertas. Elige la que vas a responder.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((evaluation) => (
          <button
            key={evaluation.id}
            type="button"
            className="grid cursor-pointer gap-1.5 rounded-xl border border-l-4 border-app border-l-primary bg-surface p-5 text-left transition hover:shadow-md"
            onClick={() => setChosen(evaluation.id)}
          >
            <strong className="text-base text-app">{evaluation.name}</strong>
            <small className="text-xs text-app-muted">{evaluation.categories} {evaluation.categories === 1 ? 'categoría' : 'categorías'} · {evaluation.criteria} preguntas</small>
            {evaluation.closes_on && <small className="text-xs text-app-muted">{evaluation.remaining === 0 ? 'Cerró' : 'Cierra'} el {formatDay(evaluation.closes_on)}</small>}
            {evaluation.remaining === 0 && <small className="text-xs font-medium text-app-muted">Completada este mes</small>}
            {evaluation.remaining > 0 && <small className="text-xs font-medium text-primary">{evaluation.remaining} por evaluar</small>}
          </button>
        ))}
      </div>
      {pageCount > 1 && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button type="button" variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>
            Anterior
          </Button>
          <span className="text-sm text-app-muted">{page}/{pageCount}</span>
          <Button type="button" variant="secondary" size="sm" disabled={page === pageCount} onClick={() => setPage((current) => current + 1)}>
            Siguiente
          </Button>
        </div>
      )}
    </div>
  )
}
