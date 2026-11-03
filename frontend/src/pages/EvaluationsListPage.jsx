import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Eye, EyeOff, LockKeyhole, Pencil } from 'lucide-react'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EvaluationProgramEditor } from '../components/EvaluationProgramFields'
import { ALERT_ERROR, PAGE_SUBTITLE, PAGE_TITLE, TH } from '../components/ui/styles'
import { useAuth } from '../context/AuthContext'
import { api, errorMessage } from '../lib/api'
import { formatDay } from '../lib/dates'
import { ratingLabel } from '../lib/ratingScales'

// Ojo: este nombre sombrea el global `URL` del navegador dentro de este módulo.
const URL = '/questions/evaluations/'
// Filas por página de la tabla (el paginado es en cliente; la API devuelve la lista completa).
const PAGE_SIZE = 4
// Mapea el `status` calculado por el backend (disponible/cerrada, incluye cierre por fecha) a su badge.
const STATUS = {
  available: { label: 'Disponible', tone: 'success' },
  closed: { label: 'Cerrada', tone: 'neutral' },
}

// Modal propio renderizado en document.body (portal) para escapar del overflow de la tabla; se cierra al hacer clic en el fondo.
function Modal({ title, onClose, children }) {
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3 sm:p-6"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-surface shadow-xl"
      >
        <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-app bg-surface px-4 py-3 sm:px-6">
          <h2 className="min-w-0 break-words text-lg font-semibold text-app">{title}</h2>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cerrar</Button>
        </div>
        <div className="p-4 sm:p-6">{children}</div>
      </section>
    </div>,
    document.body,
  )
}

// Detalle de solo lectura: estructura del formulario + respuestas recibidas (visión de jefe/administrador).
function EvaluationDetails({ evaluation }) {
  const [details, setDetails] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Bandera anti-carrera: evita actualizar estado si el modal se cerró antes de que respondiera la API.
    let current = true
    Promise.all([
      // include_inactive=1: trae también preguntas desactivadas para poder nombrar criterios de respuestas antiguas.
      api(`/questions/form/?evaluation=${evaluation.id}&include_inactive=1`),
      api(`/questions/submissions/?evaluation=${evaluation.id}`),
    ])
      .then(([categories, submissions]) => {
        if (current) setDetails({ categories, submissions })
      })
      .catch((e) => {
        if (current) setError(errorMessage(e))
      })
    return () => { current = false }
  }, [evaluation.id])

  if (error) return <div role="alert" className={ALERT_ERROR}>{error}</div>
  if (!details) return <p className="p-4 text-sm text-app-muted">Cargando categorías, preguntas y respuestas...</p>

  // code -> nombre, para mostrar texto en lugar del código en cada respuesta.
  const criterionNames = Object.fromEntries(details.categories.flatMap((category) => category.criteria.map((criterion) => [criterion.code, criterion.name])))

  return (
    <div className="grid gap-5 p-4">
      <section>
        <h3 className="font-semibold text-app">Categorías y preguntas</h3>
        {details.categories.length === 0 ? <p className="mt-2 text-sm text-app-muted">Esta evaluación aún no tiene categorías.</p> : (
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            {details.categories.map((category) => (
              <div key={category.code} className="rounded-lg border border-app bg-surface p-3">
                <h4 className="font-medium text-app">{category.name}</h4>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-app-muted">
                  {category.criteria.map((criterion) => <li key={criterion.code}>{criterion.name}</li>)}
                </ol>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3 className="font-semibold text-app">Respuestas recibidas ({details.submissions.length})</h3>
        {details.submissions.length === 0 ? <p className="mt-2 text-sm text-app-muted">Aún no hay respuestas para esta evaluación.</p> : (
          <div className="mt-2 grid gap-2">
            {details.submissions.map((submission) => {
              // Agrupa las respuestas planas por categoría conservando el orden de aparición.
              const byCategory = submission.answers.reduce((groups, answer) => {
                const group = groups.get(answer.category) ?? []
                group.push(answer)
                groups.set(answer.category, group)
                return groups
              }, new Map())
              return (
                <details key={`${submission.collaborator}-${submission.personal}-${submission.created_at}`} className="rounded-lg border border-app bg-surface">
                  <summary className="cursor-pointer px-3 py-2.5 text-sm text-app">
                    <strong>{submission.collaborator_name}</strong> evaluó a <strong>{submission.personal_name}</strong>
                    <span className="ml-2 text-app-muted">· {new Date(submission.created_at).toLocaleDateString('es-CO')} · Promedio {submission.average ?? '—'}</span>
                  </summary>
                  <div className="grid gap-3 border-t border-app px-3 py-3">
                    {[...byCategory.entries()].map(([categoryCode, answers]) => {
                      const categoryName = details.categories.find((category) => category.code === categoryCode)?.name ?? categoryCode
                      return (
                        <div key={categoryCode}>
                          <h4 className="text-sm font-medium text-app">{categoryName}</h4>
                          <ul className="mt-1 grid gap-1 text-sm text-app-muted">
                            {answers.map((answer) => (
                              <li key={answer.criterion} className="flex flex-wrap justify-between gap-2">
                                <span>{criterionNames[answer.criterion] ?? answer.criterion}</span>
                                {/* Las escalas descriptivas guardan un número; se traduce a su etiqueta textual. */}
                                <span className="font-medium text-app">{evaluation.rating_type.startsWith('descriptive') ? ratingLabel(evaluation.rating_type, answer.score) : answer.score}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )
                    })}
                  </div>
                </details>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}

function EvaluationDetailsModal({ evaluation, onClose }) {
  return (
    <Modal title={evaluation.name} onClose={onClose}>
      <EvaluationDetails evaluation={evaluation} />
    </Modal>
  )
}

// Editar la programación (áreas, personas, fecha de cierre, límite) de una evaluación ya
// creada. A diferencia de «Programar evaluación», aquí la evaluación viene fija: no se puede
// cambiar cuál se está editando.
function EvaluationProgramEditModal({ evaluation, staff, onClose, onSaved }) {
  return (
    <Modal title={`Editar programación — ${evaluation.name}`} onClose={onClose}>
      <EvaluationProgramEditor
        key={evaluation.id}
        evaluation={evaluation}
        staff={staff}
        onSaved={(updated) => {
          onSaved(updated)
          onClose()
        }}
      />
    </Modal>
  )
}

// Fila de la tabla. Una evaluación cerrada ya no se puede editar ni cerrar de nuevo (solo ver detalle), salvo para el superadmin.
function Row({ evaluation, onSave, busy, expanded, onToggle, onEditProgram }) {
  const status = STATUS[evaluation.status]
  const { user } = useAuth()
  const isClosed = evaluation.status === 'closed'
  const canEdit = !isClosed || user.role === 'superadmin'

  return (
    <>
      <tr className="align-top">
        <td className="break-words px-2 py-3 font-semibold text-app sm:px-3">
          {evaluation.name}
          <span className="block text-xs font-normal text-app-muted">ID: {evaluation.id}</span>
        </td>
        <td className="px-1 py-3 text-center sm:px-3">{evaluation.categories}</td>
        <td className="px-1 py-3 text-center sm:px-3">{evaluation.criteria}</td>
        <td className="px-1 py-3 text-center sm:px-3">{evaluation.answers}</td>
        <td className="break-words px-2 py-3 text-center align-middle text-app-muted sm:px-3">
          {evaluation.evaluated_by?.length ? evaluation.evaluated_by.join(', ') : '—'}
        </td>
        <td className="whitespace-nowrap px-2 py-3 text-center align-middle sm:px-3">
          {evaluation.closes_on ? formatDay(evaluation.closes_on) : 'Sin fecha'}
          <br />
          {/* Regla de negocio: la fecha de cierre es inclusiva; cierra al terminar ese día. */}
          <small className="whitespace-nowrap text-xs leading-snug text-app-muted">Se cierra al terminar ese día (12:00 de la noche)</small>
        </td>
        <td className="px-1 py-3 text-center align-middle sm:px-3"><Badge tone={status.tone}>{status.label}</Badge></td>
        <td className="px-1 py-3 align-middle sm:px-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <Button
              type="button"
              variant="secondary"
              size="xs"
              className="h-9 w-9 px-0"
              aria-label={expanded ? 'Ocultar detalle' : 'Ver detalle'}
              title={expanded ? 'Ocultar detalle' : 'Ver detalle'}
              onClick={onToggle}
            >
              {expanded ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
            </Button>
            {canEdit && (
              <>
                <Button
                  type="button"
                  variant="secondary"
                  size="xs"
                  className="h-9 w-9 px-0"
                  aria-label="Editar programación"
                  title="Editar programación (áreas, personas, fecha de cierre y límite)"
                  onClick={onEditProgram}
                >
                  <Pencil size={16} aria-hidden="true" />
                </Button>
                {!isClosed && <Button
                  type="button"
                  variant="secondary"
                  size="xs"
                  className="h-9 w-9 px-0"
                  aria-label="Cerrar evaluación"
                  title="Cerrar evaluación"
                  disabled={busy}
                  onClick={() => onSave(evaluation, { is_available: false })}
                >
                  <LockKeyhole size={16} aria-hidden="true" />
                </Button>}
              </>
            )}
          </div>
        </td>
      </tr>
      {expanded && <EvaluationDetailsModal evaluation={evaluation} onClose={onToggle} />}
    </>
  )
}

/**
 * Listado de evaluaciones del jefe (GET /questions/evaluations/). Permite ver detalle, editar la
 * programación y cerrar manualmente (PATCH is_available=false).
 */
export function EvaluationsListPage() {
  const [evaluations, setEvaluations] = useState(null)
  const [staff, setStaff] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState(null)
  const [editingProgram, setEditingProgram] = useState(null)

  useEffect(() => {
    let current = true
    let intervalId
    // Refresco ligero: solo actualiza el contador de respuestas (no pisa ediciones locales del resto de campos).
    const refreshAnswerCounts = async () => {
      try {
        const latest = await api(URL)
        if (!current) return
        setEvaluations((existing) => existing?.map((evaluation) => {
          const updated = latest.find((item) => item.id === evaluation.id)
          return updated ? { ...evaluation, answers: updated.answers, evaluated_by: updated.evaluated_by } : evaluation
        }))
      } catch (e) {
        if (current) setError(errorMessage(e))
      }
    }

    Promise.all([api(URL), api('/users/staff-candidates/')])
      .then(([list, candidates]) => {
        if (!current) return
        setEvaluations(list)
        setStaff(candidates)
        // Se programa tras la carga inicial: sondeo cada 15 s y al volver a enfocar la pestaña.
        intervalId = window.setInterval(refreshAnswerCounts, 15000)
        window.addEventListener('focus', refreshAnswerCounts)
      })
      .catch((e) => {
        if (current) setError(errorMessage(e))
      })
    return () => {
      current = false
      window.clearInterval(intervalId)
      window.removeEventListener('focus', refreshAnswerCounts)
    }
  }, [])

  // PATCH y recarga completa: el estado (disponible/cerrada) lo deriva el backend, no se calcula aquí.
  async function save(evaluation, body) {
    setError(null)
    setBusy(true)
    try {
      await api(`${URL}${evaluation.id}/`, { method: 'PATCH', body })
      setEvaluations(await api(URL))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  function updateEvaluationInList(updated) {
    setEvaluations((current) => current.map((evaluation) => evaluation.id === updated.id ? updated : evaluation))
  }

  // Disponibles primero y cerradas al final; dentro de cada grupo, las más nuevas (id mayor) arriba.
  const sortedEvaluations = [...(evaluations ?? [])].sort(
    (a, b) => (a.status === 'closed') - (b.status === 'closed') || b.id - a.id,
  )
  const pageCount = Math.max(1, Math.ceil(sortedEvaluations.length / PAGE_SIZE))
  const pageEvaluations = sortedEvaluations.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // Al paginar se cierra el detalle abierto para no dejar un modal de una fila que ya no se ve.
  function changePage(nextPage) {
    setPage(nextPage)
    setExpanded(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className={PAGE_TITLE}>Lista de evaluaciones</h1>
        <p className={PAGE_SUBTITLE}>
          Consulta las categorías, preguntas y respuestas de cada evaluación. El jefe define la fecha de cierre, las áreas y las personas a evaluar; los colaboradores pueden responder hasta el final de ese día.
        </p>
      </div>

      {error && <div role="alert" className={ALERT_ERROR}>{error}</div>}
      {!evaluations && !error && <p className="text-sm text-app-muted">Cargando...</p>}
      {evaluations && evaluations.length === 0 && <Card className="text-app-muted">Aún no hay evaluaciones. Crea la primera en «Configurar».</Card>}

      {evaluations && evaluations.length > 0 && (
        <>
          <Card padding="sm">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1450px] table-fixed text-sm">
                <colgroup>
                  <col className="w-[250px]" />
                  <col className="w-[110px]" />
                  <col className="w-[110px]" />
                  <col className="w-[110px]" />
                  <col className="w-[200px]" />
                  <col className="w-[360px]" />
                  <col className="w-[120px]" />
                  <col className="w-[230px]" />
                </colgroup>
                <thead>
                  <tr className="border-b border-app">
                    <th className={`${TH} whitespace-nowrap px-2 sm:px-3`}>Evaluación</th>
                    <th className={`${TH} whitespace-nowrap px-1 sm:px-2`} style={{ textAlign: 'center' }}>Categorías</th>
                    <th className={`${TH} whitespace-nowrap px-1 sm:px-2`} style={{ textAlign: 'center' }}>Preguntas</th>
                    <th className={`${TH} whitespace-nowrap px-1 sm:px-2`} style={{ textAlign: 'center' }}>Respuestas</th>
                    <th className={`${TH} whitespace-nowrap px-2 sm:px-3`} style={{ textAlign: 'center' }}>Evaluado por</th>
                    <th className={`${TH} whitespace-nowrap px-2 sm:px-3`} style={{ textAlign: 'center' }}>Fecha de cierre</th>
                    <th className={`${TH} whitespace-nowrap px-1 sm:px-2`} style={{ textAlign: 'center' }}>Estado</th>
                    <th className={`${TH} whitespace-nowrap px-1 sm:px-2`} style={{ textAlign: 'center' }}>Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-(--border)">
                  {pageEvaluations.map((evaluation) => (
                    <Row
                      key={evaluation.id}
                      evaluation={evaluation}
                      onSave={save}
                      busy={busy}
                      expanded={expanded === evaluation.id}
                      onToggle={() => setExpanded((current) => current === evaluation.id ? null : evaluation.id)}
                      onEditProgram={() => setEditingProgram(evaluation)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          {evaluations.length > 0 && (
            <div className="flex items-center justify-center gap-3">
              <Button type="button" variant="secondary" size="sm" disabled={page === 1} onClick={() => changePage(page - 1)}>Anterior</Button>
              <span className="text-sm text-app-muted">{page}/{pageCount}</span>
              <Button type="button" variant="secondary" size="sm" disabled={page === pageCount} onClick={() => changePage(page + 1)}>Siguiente</Button>
            </div>
          )}
        </>
      )}

      {editingProgram && (
        <EvaluationProgramEditModal
          evaluation={editingProgram}
          staff={staff}
          onClose={() => setEditingProgram(null)}
          onSaved={updateEvaluationInList}
        />
      )}
    </div>
  )
}
