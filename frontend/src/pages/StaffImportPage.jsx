import { useId, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ALERT_ERROR, FIELD, LABEL, PAGE_TITLE } from '../components/ui/styles'
import { api, errorMessage } from '../lib/api'

// Tarjeta para subir un archivo y mostrar el resultado de la carga. `children` son campos extra del formulario.
/**
 * Sube un archivo por multipart (FormData) a `path` y pinta el informe del backend: creados, omitidos
 * (ya existían; la carga es idempotente), filas con error y, en la carga de personal, las credenciales
 * temporales. `extra` agrega campos de formulario opcionales (se omiten los vacíos).
 */
function UploadCard({ title, hint, accept, path, extra = {}, unit, submitLabel, children }) {
  const input = useRef(null)
  const inputId = useId()
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError(null)
    setResult(null)
    setBusy(true)
    try {
      // Con FormData no se fija Content-Type a mano: el navegador añade el boundary.
      const body = new FormData()
      body.append('file', file)
      Object.entries(extra).forEach(([key, value]) => value && body.append(key, value))
      setResult(await api(path, { method: 'POST', body }))
      setFile(null)
      if (input.current) input.current.value = ''
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  function clearFile() {
    setFile(null)
    if (input.current) input.current.value = ''
  }

  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <h3 className="text-base font-semibold text-app">{title}</h3>
          <p className="mt-0.5 text-sm text-app-muted">{hint}</p>
        </div>
        {children}
        <div className={LABEL}>
          <span>Archivo</span>
          <div className={`${FIELD} flex items-center gap-3`}>
            <input
              ref={input}
              id={inputId}
              className="sr-only peer"
              type="file"
              accept={accept}
              onChange={(e) => setFile(e.target.files[0] || null)}
            />
            <span className="group relative z-0 inline-flex rounded-lg peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary hover:z-30 focus-within:z-30">
              <label
                htmlFor={inputId}
                aria-label="Elegir archivo"
                aria-describedby={`${inputId}-tooltip`}
                className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg bg-primary text-white hover:bg-primary-dark"
              >
                <Upload size={17} aria-hidden="true" />
              </label>
              <span
                id={`${inputId}-tooltip`}
                role="tooltip"
                className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-max max-w-[calc(100vw-2rem)] whitespace-normal break-words rounded-md bg-gray-900 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 sm:max-w-56"
              >
                Selecciona el archivo que vas a cargar
              </span>
            </span>
            <span className="min-w-0 flex-1 truncate text-app-muted">
              {file?.name || 'No se ha seleccionado ningún archivo'}
            </span>
            {file && (
              <button
                type="button"
                className="shrink-0 rounded-md px-2 py-1 text-sm font-medium text-app-muted hover:bg-app/5 hover:text-app focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                onClick={clearFile}
                aria-label={`Quitar archivo ${file.name}`}
              >
                Quitar
              </button>
            )}
          </div>
        </div>
        <div className="flex justify-end">
          <Button type="submit" disabled={!file || busy}>{busy ? 'Guardando...' : submitLabel}</Button>
        </div>

        {error && <div role="alert" className={ALERT_ERROR}>{error}</div>}

        {result && (
          <div className="space-y-1 text-sm text-app">
            <h4 className="text-sm font-semibold">Resultado de la carga</h4>
            {result.evaluations_created?.length > 0 && (
              <p>Nombres creados: {result.evaluations_created.join(', ')}</p>
            )}
            <p>{unit} creados: <strong>{result.created}</strong></p>
            {result.criteria_created != null && <p>Preguntas creadas: <strong>{result.criteria_created}</strong></p>}
            <p>
              Ya existían (no se duplicaron): <strong>{result.skipped}</strong>
              {result.skipped_documents?.length > 0 && <span className="text-app-muted"> — {result.skipped_documents.join(', ')}</span>}
            </p>
            {result.errors.length > 0 && (
              <>
                <p>Filas con problemas (no se cargaron): <strong>{result.errors.length}</strong></p>
                <ul className="list-disc pl-5 text-red-700 dark:text-red-300">
                  {result.errors.map((message) => <li key={message}>{message}</li>)}
                </ul>
              </>
            )}
            {/* Seguridad: el backend entrega las contraseñas temporales una sola vez; no se persisten en el cliente. */}
            {result.initial_credentials?.length > 0 && (
              <section className="mt-4 space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-950">
                <h4 className="font-semibold">Credenciales temporales — guárdalas ahora</h4>
                <p>
                  Se muestran solo en este resultado. Entrégalas directamente a cada persona; deberán
                  cambiarlas al iniciar sesión.
                </p>
                <ul className="space-y-1">
                  {result.initial_credentials.map(({ username, password }) => (
                    <li key={username} className="break-all">
                      <strong>{username}</strong>: <code>{password}</code>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </form>
    </Card>
  )
}

// Carga masiva (solo jefe/administración): personal (crea usuarios, usuario = documento) y evaluaciones (estructura de preguntas).
export function StaffImportPage() {
  return (
    <div className="space-y-6">
      <h1 className={PAGE_TITLE}>Cargar datos</h1>

      <UploadCard
        title="Cargar personal"
        submitLabel="Guardar personal"
        accept=".xlsx"
        path="/users/import/"
        unit="Personas"
        hint="Excel (.xlsx) con las columnas: Número de documento, Nombres, Apellidos (opcional), Área y Cargo. Si un documento ya existe, no se duplica ni se modifica. El documento es el usuario; las contraseñas temporales únicas se mostrarán una sola vez al completar la carga."
      />

      <UploadCard
        title="Cargar evaluaciones"
        submitLabel="Guardar evaluaciones"
        accept=".xlsx,.csv"
        path="/questions/import/"
        unit="Evaluaciones"
        hint="Excel (.xlsx) o CSV con una fila por pregunta y estas columnas: evaluation (nombre), category (categoría) y question (texto de la pregunta). Repite el nombre de evaluación y la categoría en las filas que correspondan. Puedes cargar varias evaluaciones en un archivo; las que ya existan se omiten."
      />
    </div>
  )
}
