import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams } from 'react-router-dom'
import { ScoreTable } from '../components/ScoreTable'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ALERT_ERROR, PAGE_SUBTITLE, PAGE_TITLE } from '../components/ui/styles'
import { api, errorMessage } from '../lib/api'
import { useEvaluationForms } from '../lib/useEvaluationForms'

// Envíos por página (cada uno incluye una tabla completa de criterios, por eso son pocos).
const PAGE_SIZE = 2

// Paginador reutilizable (exportado). `loading` lo deshabilita mientras se cargan datos.
export function ReviewPagination({ page, totalPages, loading, setPage }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-3 text-app-muted">
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded-md border border-app px-3 py-1.5 text-sm text-app disabled:opacity-50"
        disabled={page <= 1 || loading}
          onClick={() => setPage((current) => Math.max(1, current - 1))}
        >
          Anterior
        </button>
        <span className="px-2 text-app">{page}/{totalPages}</span>
        <button
          type="button"
          className="rounded-md border border-app px-3 py-1.5 text-sm text-app disabled:opacity-50"
          disabled={page >= totalPages || loading}
          onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
        >
          Siguiente
        </button>
      </div>
    </div>
  )
}


/**
 * Contenido compartido por la página /review y por el modal de Resultados. Con `onClose` se renderiza
 * compacto (modo modal). Lista los envíos (cada colaborador evaluando a un compañero) filtrados por
 * evaluación y/o persona evaluada; el backend limita lo visible según el rol del usuario.
 */
function ReviewContent({ evaluation, personal, onClose }) {
  const [submissions, setSubmissions] = useState(null)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const firstReviewRef = useRef(null)
  // Evita hacer scroll en el primer render; solo se desplaza al cambiar de página.
  const firstRender = useRef(true)

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    firstReviewRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' })
  }, [page])

  useEffect(() => {
    const params = new URLSearchParams()
    if (evaluation) params.set('evaluation', evaluation)
    if (personal) params.set('personal', personal)
    const query = params.toString()
    api(`/questions/submissions/${query ? `?${query}` : ''}`)
      .then(setSubmissions)
      .catch((e) => setError(errorMessage(e)))
  }, [evaluation, personal])

  // Estructura (categorías/criterios) por evaluación, necesaria para pintar cada ScoreTable.
  const forms = useEvaluationForms(submissions)
  const count = submissions?.length ?? 0
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE))
  const startIndex = (page - 1) * PAGE_SIZE
  const pageSubmissions = (submissions || []).slice(startIndex, startIndex + PAGE_SIZE)

  // Un envío no tiene id propio en la API; se identifica por la combinación de estos campos.
  const keyOf = (item) => `${item.evaluation}:${item.collaborator}:${item.personal}:${item.created_at}`

  return (
    <div className={onClose ? 'space-y-4 p-4 sm:p-6' : 'space-y-6'}>
      <div>
        <h1 className={onClose ? 'text-lg font-semibold text-app' : PAGE_TITLE}>Detalle de evaluaciones</h1>
        {!onClose && <p className={PAGE_SUBTITLE}>Los colaboradores califican a sus compañeros; aquí consultas lo que enviaron. La puntuación final es el promedio de las notas.</p>}
      </div>

      {error && <div role="alert" className={ALERT_ERROR}>{error}</div>}
      {!submissions && !error && <p className="text-sm text-app-muted">Cargando...</p>}
      {submissions && submissions.length === 0 && <Card className="text-app-muted">Aún no hay evaluaciones enviadas.</Card>}

      {pageSubmissions.map((item, index) => (
        <Card ref={index === 0 ? firstReviewRef : null} key={keyOf(item)} className="scroll-mt-20 border-l-4 border-l-primary shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Badge tone="primary" className="mb-1.5">{item.evaluation_name}</Badge>
              <h3 className="text-base font-semibold text-app">{item.collaborator_name} → {item.personal_name}</h3>
              <p className="text-sm text-app-muted">{item.area} · {new Date(item.created_at).toLocaleDateString('es-CO')}</p>
            </div>
            <div className="flex flex-col items-end">
              <small className="text-xs text-app-muted">Promedio</small>
              <strong className="text-3xl font-bold text-primary">{item.average ?? '—'}</strong>
            </div>
          </div>

          <ScoreTable
            name={keyOf(item)}
            categories={forms[item.evaluation] || []}
            scores={Object.fromEntries(item.answers.map((a) => [a.criterion, a.score]))}
            ratingType={item.rating_type}
          />
        </Card>
      ))}
      {count > 0 && (
        <ReviewPagination
          page={page}
          totalPages={totalPages}
          loading={!submissions && !error}
          setPage={setPage}
        />
      )}
    </div>
  )
}

// Versión de página completa: los filtros vienen en la URL (?evaluation=&personal=). Nótese que no está
// registrada en App.jsx; hoy el detalle se consulta desde el modal de Resultados.
export function ReviewPage() {
  const [searchParams] = useSearchParams()
  const evaluation = searchParams.get('evaluation') || ''
  const personal = searchParams.get('personal') || ''
  return (
    <ReviewContent
      // key: reinicia el estado (página, datos) cuando cambian los filtros.
      key={`${evaluation}:${personal}`}
      evaluation={evaluation}
      personal={personal}
    />
  )
}

// Modal accesible (portal, cierre con Escape o clic en el fondo) que envuelve ReviewContent.
export function ReviewModal({ evaluation, personal, onClose }) {
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3 sm:p-6"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-modal-title"
        className="max-h-[90vh] w-full max-w-6xl overflow-y-auto rounded-xl bg-surface shadow-xl"
      >
        <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-app bg-surface px-4 py-3 sm:px-6">
          <h2 id="review-modal-title" className="text-lg font-semibold text-app">Detalle de evaluaciones</h2>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cerrar</Button>
        </div>
        <ReviewContent evaluation={evaluation} personal={personal} onClose={onClose} />
      </section>
    </div>,
    document.body,
  )
}
