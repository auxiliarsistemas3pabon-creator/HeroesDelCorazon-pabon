// Cliente de la API. Las cookies httpOnly viajan solas (credentials) y las
// peticiones que modifican datos llevan el token CSRF de la cookie `csrftoken`.
const BASE = '/api/v1'

// Django exige el token CSRF en cabecera para métodos no seguros; se lee de la cookie que emite el backend.
function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

// Convierte un error lanzado por `api` en texto para el usuario. Soporta el formato de DRF:
// { detail: '...' } o { campo: ['mensaje'] } (se toma el primer mensaje).
export function errorMessage(error, fallback = 'Ocurrió un error') {
  // 502/503/504: el backend se está reiniciando o no responde; fetch sin status: no hay conexión.
  if (error?.status >= 502) return 'El servidor no está disponible en este momento. Intenta de nuevo en unos segundos.'
  if (error instanceof TypeError) return 'No hay conexión con el servidor. Revisa tu red e intenta de nuevo.'
  const data = error?.data
  if (!data) return fallback
  if (typeof data.detail === 'string') return data.detail
  const first = Object.values(data).flat()[0]
  return typeof first === 'string' ? first : fallback
}

// Petición sin reintentos. Lanza Error con `status` y `data` (cuerpo JSON del error) para errorMessage.
// `body` puede ser objeto (se serializa a JSON) o FormData (subida de archivos).
async function send(path, { method = 'GET', body } = {}) {
  const headers = {}
  const isForm = body instanceof FormData // archivos: el navegador pone el Content-Type con su boundary
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') headers['X-CSRFToken'] = csrfToken()

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: body === undefined || isForm ? body : JSON.stringify(body),
  })
  const data = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw Object.assign(new Error(`HTTP ${response.status}`), { status: response.status, data })
  return data
}

// Punto de entrada para llamar al backend; `path` es relativo a /api/v1. Devuelve el JSON (null en 204).
export async function api(path, options) {
  try {
    return await send(path, options)
  } catch (error) {
    // Access token vencido: intenta renovarlo una vez y repite la petición.
    if (error.status === 401 && !path.startsWith('/auth/')) {
      await send('/auth/refresh/', { method: 'POST' })
      return send(path, options)
    }
    throw error
  }
}