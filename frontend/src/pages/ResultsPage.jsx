import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Download, Eye } from 'lucide-react'
import * as XLSX from 'xlsx'
import { AutocompleteSelect } from '../components/ui/AutocompleteSelect'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EvaluationSelect } from '../components/ui/EvaluationSelect'
import { DateRangeFilter } from '../components/ui/DateRangeFilter'
import { ALERT_ERROR, LABEL, PAGE_SUBTITLE, PAGE_TITLE, TH } from '../components/ui/styles'
import { api, errorMessage } from '../lib/api'
import { ReviewModal } from './ReviewPage'


// Resumen por persona evaluada: filas con `by_category` y `average`, más la lista de categorías (columnas dinámicas).
// Ojo: URL sombrea el global del navegador.
// YYYY-MM-DD -> DD/MM/YYYY
const formatShortDate = (iso) => iso.split('-').reverse().join('/')

const URL = '/questions/results-summary/'
// Filas por página; el filtrado, orden y paginado se hacen en cliente sobre `data.rows`.
const PAGE_SIZE = 4

// Normaliza para búsquedas sin tildes ni mayúsculas ("Pérez" == "perez"): NFD separa las marcas diacríticas y se eliminan.
function normalizeSearch(value) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLocaleLowerCase()
}

// Encabezado ordenable accesible (aria-sort); la flecha activa se resalta con el color primario.
function SortableHeader({ children, sortKey, activeSort, direction, onSort, align = 'left', className = '' }) {
  const active = activeSort === sortKey
  const ariaSort = active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'

  return (
    <th className={`${TH} whitespace-nowrap ${className}`} aria-sort={ariaSort}>
      <button
        type="button"
        className={`inline-flex items-center gap-1.5 hover:text-app ${align === 'center' ? 'mx-auto' : ''}`}
        onClick={() => onSort(sortKey)}
      >
        {children}
        <span className="inline-flex items-center gap-0.5" aria-hidden="true">
          <ChevronUp
            size={14}
            className={active && direction === 'asc' ? 'text-primary' : ''}
          />
          <ChevronDown
            size={14}
            className={active && direction === 'desc' ? 'text-primary' : ''}
          />
        </span>
      </button>
    </th>
  )
}

// Resultados (solo jefe): lo que obtuvo cada persona, por categoría y promedio general.
export function ResultsPage() {
  const [evaluations, setEvaluations] = useState(null)
  const [evaluation, setEvaluation] = useState('')
  const [area, setArea] = useState('')
  const [person, setPerson] = useState('')
  const [position, setPosition] = useState('')
  const [dates, setDates] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [detail, setDetail] = useState(null)
  const [sortBy, setSortBy] = useState('name')
  const [sortDirection, setSortDirection] = useState('asc')

  // useCallback: ReviewModal registra un listener de Escape que depende de onClose; una referencia estable evita re-suscribirlo en cada render.
  const closeDetail = useCallback(() => setDetail(null), [])

  useEffect(() => {
    api('/questions/evaluations/?mine=1')
      .then(setEvaluations)
      .catch((e) => setError(errorMessage(e)))
  }, [])

  // Sin evaluación elegida el backend devuelve una por defecto (`result.evaluation`) y aquí se adopta como selección.
  // 'all' (opción "Todas") consolida todas las evaluaciones del jefe.
  useEffect(() => {
    const params = new URLSearchParams()
    if (evaluation) params.set('evaluation', evaluation)
    if (dates.from) params.set('date_from', dates.from)
    if (dates.to) params.set('date_to', dates.to)
    const query = params.toString()
    // `ignore`: si cambia el filtro antes de responder, la respuesta vieja no pisa a la nueva.
    let ignore = false
    api(`${URL}${query ? `?${query}` : ''}`)
      .then((result) => {
        if (ignore) return
        setError(null)
        setData(result)
        if (!evaluation && result.evaluation) setEvaluation(String(result.evaluation.id))
      })
      .catch((e) => { if (!ignore) setError(errorMessage(e)) })
    return () => { ignore = true }
  }, [evaluation, dates])

  // Los filtros Área/Persona/Cargo se derivan de las filas ya cargadas (en cascada: persona y cargo dependen del área).
  const areas = [...new Set((data?.rows || []).map((row) => row.area).filter(Boolean))].sort()
  const inArea = (data?.rows || []).filter((row) => !area || row.area === area)
  const positions = [...new Set(inArea.map((row) => row.position).filter(Boolean))].sort()
  const people = [...new Map(inArea.map((row) => [String(row.personal), row])).values()]
    .sort((first, second) => first.name.localeCompare(second.name, 'es'))
  const normalizedPerson = normalizeSearch(person)
  const normalizedPosition = normalizeSearch(position)
  const rows = inArea.filter((row) =>
    normalizeSearch(row.name).includes(normalizedPerson)
    && normalizeSearch(row.position || '').includes(normalizedPosition),
  )

  // Primer clic: columnas numéricas empiezan en descendente (mejores primero), texto en ascendente.
  const handleSort = (key) => {
    const numeric = key === 'average' || key.startsWith('category:')
    if (sortBy === key) {
      setSortDirection((current) => current === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(key)
      setSortDirection(numeric ? 'desc' : 'asc')
    }
    setPage(1)
  }

  const sortedRows = [...rows].sort((first, second) => {
    if (sortBy === 'name' || sortBy === 'area' || sortBy === 'performed_at') {
      const comparison = String(first[sortBy] || '').localeCompare(String(second[sortBy] || ''), 'es', {
        sensitivity: 'base',
        numeric: true,
      })
      return sortDirection === 'asc' ? comparison : -comparison
    }

    // Orden numérico: los valores vacíos o no numéricos (sin respuestas en esa categoría) siempre van al final.
    const key = sortBy === 'average' ? 'average' : sortBy.slice('category:'.length)
    const firstValue = sortBy === 'average' ? first.average : first.by_category[key]
    const secondValue = sortBy === 'average' ? second.average : second.by_category[key]
    const firstNumber = firstValue == null ? null : Number(firstValue)
    const secondNumber = secondValue == null ? null : Number(secondValue)

    const firstMissing = firstNumber == null || !Number.isFinite(firstNumber)
    const secondMissing = secondNumber == null || !Number.isFinite(secondNumber)
    if (firstMissing || secondMissing) return firstMissing === secondMissing ? 0 : firstMissing ? 1 : -1
    return sortDirection === 'desc' ? secondNumber - firstNumber : firstNumber - secondNumber
  })
  // OJO: el total de páginas usa `rows` (filtradas) y la página sale de `sortedRows`; ambas tienen la misma longitud.
  // Exporta a .xlsx lo que muestra la tabla (evaluación elegida, filtros y orden actuales), todas las páginas.
  function downloadExcel() {
    const evaluationName = evaluations?.find((item) => String(item.id) === evaluation)?.name ?? data.evaluation?.name ?? 'Evaluación'
    const table = sortedRows.map((row) => ({
      'Persona evaluada': row.name,
      Cargo: row.position || '',
      Área: row.area || '',
      ...Object.fromEntries(data.categories.map((category) => [category.name, row.by_category[category.code] ?? ''])),
      'Promedio general': row.average ?? '',
      'Fecha de realización': row.performed_at ? formatShortDate(row.performed_at) : '',
    }))
    const book = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(book, XLSX.utils.json_to_sheet(table), 'Resultados')
    XLSX.writeFile(book, `Resultados - ${evaluationName}.xlsx`.replace(/[\\/:*?"<>|]/g, '-'))
  }

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const pageRows = sortedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)


  return (
    <div className="space-y-6">
      <div>
        <h1 className={PAGE_TITLE}>Resultados</h1>
        <p className={PAGE_SUBTITLE}>Lo que obtuvo cada persona {evaluation === 'all' ? 'en todas las evaluaciones' : 'en la evaluación elegida'}: promedio por categoría y promedio general según la escala definida para cada evaluación.</p>
      </div>

      {evaluations && evaluations.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <label className={`${LABEL} w-full sm:w-auto sm:min-w-56`}>
            Área
            <AutocompleteSelect
              value={area}
              onChange={(value) => { setArea(value); setPerson(''); setPosition(''); setPage(1) }}
              placeholder="Todas"
              options={[
                { value: '', label: 'Todas' },
                ...areas.map((name) => ({ value: name, label: name })),
              ]}
            />
          </label>
          <label className={`${LABEL} w-full sm:w-auto sm:min-w-56`}>
            Persona evaluada
            <AutocompleteSelect
              value={person}
              allowCustom
              onChange={(value) => { setPerson(value); setPage(1) }}
              placeholder="Todas"
              options={[
                { value: '', label: 'Todas' },
                ...people.map((row) => ({ key: row.personal, value: row.name, label: row.name })),
              ]}
            />
          </label>
          <label className={`${LABEL} w-full sm:w-auto sm:min-w-56`}>
            Cargo
            <AutocompleteSelect
              value={position}
              allowCustom
              onChange={(value) => { setPosition(value); setPage(1) }}
              placeholder="Todos"
              options={[
                { value: '', label: 'Todos' },
                ...positions.map((item) => ({ value: item, label: item })),
              ]}
            />
          </label>
          {/* basis-full fuerza salto de línea: la evaluación (y su fecha de cierre) va debajo de Área/Persona/Cargo. */}
          <div className="flex basis-full flex-wrap items-end gap-3">
            <EvaluationSelect
              evaluations={evaluations}
              value={evaluation}
              onChange={(value) => { setEvaluation(value); setArea(''); setPerson(''); setPosition(''); setPage(1) }}
            />
          </div>
          {/* Igual para el rango de fechas, debajo de la evaluación. */}
          <div className="flex basis-full flex-wrap items-end gap-3">
            <DateRangeFilter from={dates.from} to={dates.to} onChange={(value) => { setDates(value); setPage(1) }} />
          </div>
        </div>
      )}

      {error && <div role="alert" className={ALERT_ERROR}>{error}</div>}
      {!data && !error && <p className="text-sm text-app-muted">Cargando...</p>}
      {data && data.rows.length === 0 && <Card className="text-app-muted">Aún no hay resultados {evaluation === 'all' ? 'en las evaluaciones' : 'en esta evaluación'}.</Card>}
      {data && data.rows.length > 0 && rows.length === 0 && <Card className="text-app-muted">No hay resultados con esos filtros.</Card>}

      {data && rows.length > 0 && (
        <div className="flex justify-end">
          <Button type="button" variant="secondary" size="sm" onClick={downloadExcel}>
            <Download size={16} aria-hidden="true" /> Descargar Excel
          </Button>
        </div>
      )}

      {data && rows.length > 0 && (
        <Card padding="sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-max table-auto text-sm">
              <thead>
                <tr className="border-b border-app">
                  <SortableHeader sortKey="name" activeSort={sortBy} direction={sortDirection} onSort={handleSort} className="min-w-[220px]">
                    Persona evaluada
                  </SortableHeader>
                  <SortableHeader sortKey="area" activeSort={sortBy} direction={sortDirection} onSort={handleSort} align="center" className="min-w-[150px]">
                    Área
                  </SortableHeader>
                  {data.categories.map((category) => (
                    <SortableHeader
                      key={category.code}
                      sortKey={`category:${category.code}`}
                      activeSort={sortBy}
                      direction={sortDirection}
                      onSort={handleSort}
                      align="center"
                      className="min-w-[180px]"
                    >
                      {category.name}
                    </SortableHeader>
                  ))}
                  <SortableHeader sortKey="average" activeSort={sortBy} direction={sortDirection} onSort={handleSort} align="center" className="min-w-[160px] text-center">
                    Promedio general
                  </SortableHeader>
                  <SortableHeader sortKey="performed_at" activeSort={sortBy} direction={sortDirection} onSort={handleSort} align="center" className="min-w-[160px]">
                    Fecha de realización
                  </SortableHeader>
                  <th className={`${TH} whitespace-nowrap text-center`}>Detalle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-(--border)">
                {pageRows.map((row) => (
                  <tr key={row.personal}>
                    <td className="min-w-[220px] whitespace-nowrap px-3 py-3">
                      <strong className="font-semibold text-app">{row.name}</strong>
                      {row.position && <small className="block whitespace-normal text-xs text-app-muted">{row.position}</small>}
                    </td>
                    <td className="min-w-[150px] whitespace-nowrap px-3 py-3 text-center">{row.area || '—'}</td>
                    {data.categories.map((category) => (
                      <td key={category.code} className="min-w-[180px] whitespace-nowrap px-3 py-3 text-center">{row.by_category[category.code] ?? '—'}</td>
                    ))}
                    <td className="min-w-[160px] whitespace-nowrap px-3 py-3 text-center"><strong className="text-lg font-bold text-primary">{row.average}</strong></td>
                    <td className="min-w-[160px] whitespace-nowrap px-3 py-3 text-center">{row.performed_at ? formatShortDate(row.performed_at) : '—'}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-center">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="h-9 w-9 px-0"
                        aria-label={`Ver detalle de ${row.name}`}
                        title={`Ver detalle de ${row.name}`}
                        // '' = todas las evaluaciones (ReviewContent omite el parámetro si viene vacío).
                        onClick={() => setDetail({
                          evaluation: evaluation === 'all' ? '' : evaluation,
                          personal: String(row.personal),
                        })}
                      >
                        <Eye size={17} aria-hidden="true" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {rows.length > 0 && (
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

      {detail && (
        <ReviewModal
          // key: fuerza un modal nuevo (estado de página reiniciado) al abrir otra persona/evaluación.
          key={`${detail.evaluation}:${detail.personal}`}
          evaluation={detail.evaluation}
          personal={detail.personal}
          onClose={closeDetail}
        />
      )}
    </div>
  )
}
