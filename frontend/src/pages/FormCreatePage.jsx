import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ScoreTable } from '../components/ScoreTable'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ALERT_ERROR, CELL_INPUT, FIELD, PAGE_TITLE } from '../components/ui/styles'
import { api, errorMessage } from '../lib/api'
import { cn } from '../lib/cn'
import { formatDay } from '../lib/dates'
import { RATING_SCALES } from '../lib/ratingScales'
import { useAuth } from '../context/AuthContext'

// Ojo: URL sombrea el global del navegador. Categorías (y criterios anidados) vs. evaluaciones.
const URL = '/questions/categories/'
const EVALUATIONS = '/questions/evaluations/'
const PAGE_SIZE = 4

// La categoría nueva arranca en blanco, con 3 filas de preguntas (como las categorías actuales).
const blankCategory = () => ({ name: '', questions: ['', '', ''] })

// Modal sencillo (sin portal); se cierra al hacer clic en el fondo. Hay otro equivalente en EvaluationsListPage.
function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section role="dialog" aria-modal="true" aria-label={title} className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-xl bg-app p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-app">{title}</h2>
          <Button type="button" variant="secondary" size="sm" onClick={onClose} aria-label="Cerrar">Cerrar</Button>
        </div>
        {children}
      </section>
    </div>
  )
}

// Cuadro de texto que crece con lo que se escribe: el texto nunca queda cortado.
function AutoTextarea({ value, ...props }) {
  const ref = useRef(null)

  // Se resetea a 'auto' antes de medir; si no, el textarea nunca se encogería al borrar texto.
  useLayoutEffect(() => {
    const box = ref.current
    box.style.height = 'auto'
    box.style.height = `${box.scrollHeight}px`
  }, [value])

  return <textarea ref={ref} className={CELL_INPUT} rows={1} value={value} {...props} />
}


// Fila final: el cuadro de la nueva pregunta ocupa la columna de criterio (igual que los demás) y el botón va en acciones.
function AddQuestion({ onAdd, scoreColumns }) {
  const [text, setText] = useState('')

  function add() {
    if (!text.trim()) return
    onAdd(text)
    setText('')
  }

  return (
    <>
      <td className="min-w-40 border border-app bg-app-muted px-2.5 py-2 align-middle">
        <input
          className={CELL_INPUT}
          value={text}
          placeholder="Escribe otra pregunta"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
        />
      </td>
      <td colSpan={scoreColumns} className="border border-app bg-app-muted" />
      <td className="w-32 border border-app bg-app-muted px-2.5 py-2 align-middle">
        <Button type="button" variant="secondary" size="sm" className="whitespace-nowrap" disabled={!text.trim()} onClick={add}>
          + Agregar
        </Button>
      </td>
    </>
  )
}

// Lista de evaluaciones: cada una es un formulario aparte. El jefe crea nuevas, las abre o cierra y agrega las categorías que necesite.
/**
 * Gestor del jefe: lista sus evaluaciones (?created_by=me), crea, abre/cierra, edita y elimina.
 * El padre (FormCreatePage) es dueño de la lista y de `selected`; aquí `onChanged` recarga desde la API.
 * Las evaluaciones de un jefe no las ve otro jefe: el filtrado de propiedad lo hace el backend.
 */
function EvaluationsManager({ evaluations, selected, onSelect, onChanged, onError, modalOpen, setModalOpen }) {
  const [name, setName] = useState('')
  const [ratingType, setRatingType] = useState('')
  const [categories, setCategories] = useState([blankCategory()])
  // Estado del modal de edición: `editCategories` es una copia local con ids reales (existentes) o sin id (nuevos).
  const [editName, setEditName] = useState('')
  const [editCategories, setEditCategories] = useState([])
  const [editing, setEditing] = useState(null)
  const [editLoading, setEditLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [page, setPage] = useState(1)
  const { user } = useAuth()

  // Abiertas primero y cerradas al final (el orden relativo se conserva); se muestran PAGE_SIZE por página.
  const sorted = [...evaluations].sort((a, b) => (a.status === 'closed') - (b.status === 'closed'))
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pageEvaluations = sorted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  // Ejecuta una llamada de escritura, recarga la lista vía onChanged y devuelve true/false para que
  // el llamador decida si limpiar su estado local.
  async function act(path, options) {
    onError(null)
    setBusy(true)
    try {
      const result = await api(path, options)
      await onChanged(result)
      return true
    } catch (e) {
      onError(errorMessage(e))
      return false
    } finally {
      setBusy(false)
    }
  }

  async function create(event) {
    event.preventDefault()
    // Se descartan preguntas vacías; las categorías vacías ya las bloquea `formReady`.
    const payloadCategories = categories.map((category) => ({
      name: category.name.trim(),
      criteria: category.questions.map((question) => question.trim()).filter(Boolean),
    }))
    if (await act(EVALUATIONS, { method: 'POST', body: { name, rating_type: ratingType, categories: payloadCategories } })) {
      setName('')
      setRatingType('')
      setCategories([blankCategory()])
      setModalOpen(false)
    }
  }

  // Requisitos para crear: nombre, tipo de calificación (inmutable luego) y cada categoría con nombre y >= 1 pregunta.
  const formReady = name.trim() && Boolean(ratingType) && categories.every((category) =>
    category.name.trim() && category.questions.some((question) => question.trim()),
  )
  const selectedEvaluation = evaluations.find((evaluation) => evaluation.id === selected)

  // Adapta el borrador a la API `editor` de ScoreTable. Los `code` del borrador (draft-<cat>-<preg>) son
  // ficticios: el último segmento se usa como índice de la pregunta en `category.questions`.
  function categoryEditor(categoryIndex) {
    const category = categories[categoryIndex]
    const updateCategory = (updater) => setCategories((current) => current.map((item, index) => index === categoryIndex ? updater(item) : item))
    return {
      renderCategory: () => (
        <AutoTextarea
          placeholder={`Nombre de categoría ${categoryIndex + 1}`}
          value={category.name}
          onChange={(e) => updateCategory((item) => ({ ...item, name: e.target.value }))}
        />
      ),
      renderCriterion: (criterion) => {
        const questionIndex = Number(criterion.code.split('-').at(-1))
        return <AutoTextarea value={category.questions[questionIndex]} aria-label={`Pregunta ${questionIndex + 1}`} onChange={(e) => updateCategory((item) => ({
          ...item,
          questions: item.questions.map((question, index) => index === questionIndex ? e.target.value : question),
        }))} />
      },
      renderActions: (criterion) => {
        if (category.questions.length <= 1) return null
        const questionIndex = Number(criterion.code.split('-').at(-1))
        return <Button type="button" variant="secondary" size="sm" onClick={() => updateCategory((item) => ({ ...item, questions: item.questions.filter((_, index) => index !== questionIndex) }))}>Quitar</Button>
      },
      renderAdd: () => <AddQuestion scoreColumns={RATING_SCALES[ratingType]?.options.length ?? 5} onAdd={(text) => updateCategory((item) => ({ ...item, questions: [...item.questions, text] }))} />,
    }
  }

  // No hay endpoint transaccional: se hacen varios PATCH/POST secuenciales (nombre, categorías, preguntas).
  // Si uno falla, lo anterior ya quedó guardado; por eso se recarga al terminar. Las filas sin `id` son nuevas (POST).
  async function saveEdit(event) {
    event.preventDefault()
    if (!editing || !editName.trim() || !editCategories.every((category) =>
      category.name.trim() && category.criteria.length > 0 && category.criteria.every((criterion) => criterion.name.trim()),
    )) return
    onError(null)
    setBusy(true)
    try {
      await api(`${EVALUATIONS}${editing.id}/`, { method: 'PATCH', body: { name: editName } })
      for (const category of editCategories) {
        const criteria = category.criteria.map((criterion) => criterion.name.trim()).filter(Boolean)
        if (!category.id) {
          await api(URL, { method: 'POST', body: { evaluation: editing.id, name: category.name, criteria } })
          continue
        }
        await api(`${URL}${category.id}/`, { method: 'PATCH', body: { name: category.name } })
        for (const criterion of category.criteria) {
          if (!criterion.name.trim()) continue
          if (criterion.id) {
            await api(`/questions/criteria/${criterion.id}/`, { method: 'PATCH', body: { name: criterion.name } })
          } else {
            await api(`${URL}${category.id}/criteria/`, { method: 'POST', body: { name: criterion.name } })
          }
        }
      }
      await onChanged({ id: editing.id })
      setEditing(null)
      setEditName('')
      setEditCategories([])
    } catch (e) {
      onError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  // Carga categorías con `used` (tiene respuestas). Se necesita para decidir entre eliminar o solo desactivar.
  async function openEdit(evaluation) {
    setEditing(evaluation)
    setEditName(evaluation.name)
    setEditCategories([])
    setEditLoading(true)
    onError(null)
    try {
      const categories = await api(`${URL}?evaluation=${evaluation.id}`)
      setEditCategories(categories.map((category) => ({
        id: category.id,
        name: category.name,
        used: category.used,
        criteria: category.criteria.map((criterion) => ({ id: criterion.id, name: criterion.name, used: criterion.used })),
      })))
    } catch (e) {
      onError(errorMessage(e))
    } finally {
      setEditLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
      <h3 className="text-base font-semibold text-app">Evaluaciones</h3>
      <p className="mt-0.5 text-sm text-app-muted">
        Cada evaluación es independiente y puede tener las categorías que necesites. El jefe define la fecha de cierre; los
        colaboradores pueden responder hasta la fecha de cierre definida por el jefe y solo ven las evaluaciones abiertas.
      </p>

      <ul className="mt-3 grid gap-2">
        {pageEvaluations.map((evaluation) => {
          // Cerrada por fecha de vencimiento (is_available sigue en true): no se puede reabrir desde aquí, hay que cambiar la fecha en «Programar».
          const automaticallyClosed = evaluation.is_available && evaluation.status === 'closed'
          // Cerrada: solo el superadmin puede editarla, reabrirla o eliminarla (el backend también lo exige).
          const locked = evaluation.status === 'closed' && user.role !== 'superadmin'
          return (
            <li
              key={evaluation.id}
              className={cn(
                'flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2.5',
                evaluation.id === selected ? 'border-primary bg-primary/5' : 'border-app',
              )}
            >
            <label className="flex min-w-56 flex-1 cursor-pointer items-center gap-2.5">
              <input
                className="accent-primary"
                type="radio"
                name="evaluation"
                checked={evaluation.id === selected}
                onChange={() => onSelect(evaluation.id)}
              />
              <span>
                <strong>{evaluation.name}</strong>{' '}
                <small className="text-xs text-app-muted">
                  {evaluation.categories} {evaluation.categories === 1 ? 'categoría' : 'categorías'} · {evaluation.criteria} preguntas ·{' '}
                  {{ available: 'Disponible', closed: 'Cerrada' }[evaluation.status]}
                  {evaluation.closes_on && ` · cierra el ${formatDay(evaluation.closes_on)}`}
                </small>
              </span>
            </label>
            <span className="flex items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy || locked || (automaticallyClosed && user.role !== 'superadmin')}
                onClick={() => act(`${EVALUATIONS}${evaluation.id}/`, { method: 'PATCH', body: { is_available: !evaluation.is_available } })}
              >
                {automaticallyClosed ? 'Cerrada' : evaluation.is_available ? 'Cerrar' : 'Habilitar'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy || locked}
                onClick={() => openEdit(evaluation)}
              >
                Editar
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy || locked}
                onClick={() =>
                  // El borrado en cascada elimina categorías, preguntas y respuestas asociadas (confirmación obligatoria).
                  window.confirm(`¿Borrar "${evaluation.name}" con todas sus categorías y preguntas?`) &&
                  act(`${EVALUATIONS}${evaluation.id}/`, { method: 'DELETE' })
                }
              >
                Eliminar
              </Button>
            </span>
            </li>
          )
        })}
      </ul>
      {pageCount > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <Button type="button" variant="secondary" size="sm" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>
            Anterior
          </Button>
          <span className="text-sm text-app-muted">{currentPage}/{pageCount}</span>
          <Button type="button" variant="secondary" size="sm" disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)}>
            Siguiente
          </Button>
        </div>
      )}
      <p className="mt-4 border-t border-app pt-3 text-sm text-app-muted">
        {evaluations.length === 0
          ? 'Aún no hay evaluaciones.'
          : selectedEvaluation
          ? <>Seleccionada: <strong className="break-words text-app">{selectedEvaluation.name}</strong>.</>
          : 'Selecciona una evaluación para continuar.'}
      </p>
      </Card>
      <Button type="button" className="self-start" onClick={() => setModalOpen(true)}>Crear evaluación</Button>
      {modalOpen && (
        <Modal title="Crear evaluación" onClose={() => { setModalOpen(false); setName(''); setRatingType(''); setCategories([blankCategory()]) }}>
          <form className="grid gap-4" onSubmit={create}>
            <input
              autoFocus
              className={CELL_INPUT}
              value={name}
              placeholder="Nombre de la nueva evaluación"
              aria-label="Nombre de la nueva evaluación"
              onChange={(e) => setName(e.target.value)}
            />
            <label className="grid gap-1.5 text-sm font-medium text-app">
              Tipo de calificación
              <select className={FIELD} value={ratingType} onChange={(e) => setRatingType(e.target.value)} required>
                <option value="" disabled>Selecciona el tipo de calificación</option>
                {Object.entries(RATING_SCALES).map(([value, scale]) => (
                  <option key={value} value={value}>{scale.label}</option>
                ))}
              </select>
            </label>
            {ratingType && <>
            <p className="text-sm text-app-muted">Agrega las categorías y preguntas que necesites{name.trim() ? ` a ${name.trim()}` : ' a esta evaluación'}. {RATING_SCALES[ratingType]?.description}</p>
            {categories.map((category, categoryIndex) => {
              const tableCategory = {
                code: `draft-category-${categoryIndex}`,
                name: category.name,
                criteria: category.questions.map((question, questionIndex) => ({ code: `draft-${categoryIndex}-${questionIndex}`, name: question })),
              }
              return (
                <Card key={categoryIndex}>
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <h3 className="font-semibold text-app">Categoría {categoryIndex + 1}</h3>
                    {categories.length > 1 && <Button type="button" variant="secondary" size="sm" onClick={() => setCategories((current) => current.filter((_, index) => index !== categoryIndex))}>Quitar categoría</Button>}
                  </div>
                  <ScoreTable categories={[tableCategory]} editor={categoryEditor(categoryIndex)} ratingType={ratingType} />
                </Card>
              )
            })}
            <Button type="button" variant="secondary" onClick={() => setCategories((current) => [...current, blankCategory()])}>+ Añadir categoría</Button>
            </>}
            <div className="flex justify-end">
              <Button type="submit" disabled={busy || !formReady}>{busy ? 'Guardando...' : 'Guardar evaluación'}</Button>
            </div>
          </form>
        </Modal>
      )}
      {editing && (
        <Modal title="Editar evaluación" onClose={() => { setEditing(null); setEditName(''); setEditCategories([]) }}>
          {editLoading ? <p className="text-sm text-app-muted">Cargando evaluación...</p> : (
            <form className="grid gap-4" onSubmit={saveEdit}>
              <p className="text-sm text-app-muted">Edita el nombre, las categorías y sus preguntas. El tipo de calificación se selecciona al crear la evaluación.</p>
              <label className="grid gap-1.5 text-sm font-medium text-app">
                Nombre de la evaluación
                <input autoFocus className={CELL_INPUT} value={editName} onChange={(e) => setEditName(e.target.value)} />
              </label>

              {editCategories.map((category, categoryIndex) => (
                <Card key={category.id ?? `new-${categoryIndex}`}>
                  <div className="flex items-end gap-3">
                    <label className="grid flex-1 gap-1.5 text-sm font-medium text-app">
                      Categoría {categoryIndex + 1}
                      <input className={CELL_INPUT} value={category.name} onChange={(e) => setEditCategories((current) => current.map((item, index) => index === categoryIndex ? { ...item, name: e.target.value } : item))} />
                    </label>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={busy}
                      onClick={async () => {
                        if (!category.id) {
                          setEditCategories((current) => current.filter((_, index) => index !== categoryIndex))
                          return
                        }
                        // Regla: lo que ya tiene respuestas no se borra (se perderían datos de reportes), solo se desactiva.
                        const action = category.used ? 'desactivar' : 'eliminar'
                        if (!window.confirm(`¿Deseas ${action} la categoría «${category.name}»?`)) return
                        const result = await act(
                          `${URL}${category.id}/`,
                          category.used ? { method: 'PATCH', body: { is_active: false } } : { method: 'DELETE' },
                        )
                        if (result) setEditCategories((current) => current.filter((item) => item.id !== category.id))
                      }}
                    >
                      Quitar categoría
                    </Button>
                  </div>
                  <div className="mt-3 grid gap-2">
                    {category.criteria.map((criterion, criterionIndex) => (
                      <div key={criterion.id ?? `new-criterion-${criterionIndex}`} className="flex items-end gap-2">
                        <label className="grid flex-1 gap-1 text-sm text-app-muted">
                          Pregunta {criterionIndex + 1}
                          <input className={CELL_INPUT} value={criterion.name} onChange={(e) => setEditCategories((current) => current.map((item, index) => index === categoryIndex ? {
                            ...item,
                            criteria: item.criteria.map((question, questionIndex) => questionIndex === criterionIndex ? { ...question, name: e.target.value } : question),
                          } : item))} />
                        </label>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={busy || category.criteria.length <= 1}
                          onClick={async () => {
                            if (!criterion.id) {
                              setEditCategories((current) => current.map((item, index) => index === categoryIndex ? {
                                ...item,
                                criteria: item.criteria.filter((_, questionIndex) => questionIndex !== criterionIndex),
                              } : item))
                              return
                            }
                            const action = criterion.used ? 'desactivar' : 'eliminar'
                            if (!window.confirm(`¿Deseas ${action} la pregunta «${criterion.name}»?`)) return
                            const result = await act(
                              `/questions/criteria/${criterion.id}/`,
                              criterion.used ? { method: 'PATCH', body: { is_active: false } } : { method: 'DELETE' },
                            )
                            if (result) setEditCategories((current) => current.map((item, index) => index === categoryIndex ? {
                              ...item,
                              criteria: item.criteria.filter((question) => question.id !== criterion.id),
                            } : item))
                          }}
                        >
                          Quitar
                        </Button>
                      </div>
                    ))}
                    <Button type="button" variant="secondary" size="sm" className="justify-self-start" onClick={() => setEditCategories((current) => current.map((item, index) => index === categoryIndex ? { ...item, criteria: [...item.criteria, { name: '' }] } : item))}>+ Añadir pregunta</Button>
                  </div>
                </Card>
              ))}
              <Button type="button" variant="secondary" onClick={() => setEditCategories((current) => [...current, { name: '', criteria: [{ name: '' }] }])}>+ Añadir categoría</Button>
              <div className="flex justify-end">
                <Button type="submit" disabled={busy || !editName.trim() || !editCategories.every((category) => category.name.trim() && category.criteria.length > 0 && category.criteria.every((criterion) => criterion.name.trim()))}>{busy ? 'Guardando...' : 'Guardar cambios'}</Button>
              </div>
            </form>
          )}
        </Modal>
      )}
    </div>
  )
}

// Pantalla «Crear evaluación» (solo jefe). Los criterios de calificación y las escalas están en lib/ratingScales.
export function FormCreatePage() {
  const [evaluations, setEvaluations] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)


  // Guarda la lista y conserva una selección válida: prioriza `pick` (recién creada/editada), luego la
  // anterior y por último la primera de la lista.
  function show(list, pick) {
    setEvaluations(list)
    setSelected((current) => [pick, current].map((id) => list.find((e) => e.id === id)).find(Boolean)?.id ?? list[0]?.id ?? null)
  }
  const reload = (pick) => api(`${EVALUATIONS}?created_by=me`).then((list) => show(list, pick))


  useEffect(() => {
    api(`${EVALUATIONS}?created_by=me`)
      .then(show)
      .catch((e) => setError(errorMessage(e)))
  }, [])

  return (
    <div className="space-y-6">
      <h1 className={PAGE_TITLE}>Crear evaluación</h1>

      {evaluations && (
        <EvaluationsManager
          evaluations={evaluations}
          selected={selected}
          onSelect={setSelected}
          onChanged={(result) => reload(result?.id)}
          onError={setError}
          modalOpen={createOpen}
          setModalOpen={setCreateOpen}
        />
      )}

      {error && <div role="alert" className={ALERT_ERROR}>{error}</div>}
    </div>
  )
}
