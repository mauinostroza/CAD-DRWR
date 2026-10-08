const BASE = import.meta.env.VITE_API_BASE ?? '/api'
export const apiBase = BASE
// La sesión viaja en una cookie HttpOnly que el navegador adjunta solo. No hay
// nada que guardar aquí: el código de la página no puede leerla, y por eso una
// vulnerabilidad de scripting tampoco podría robarla.
const CREDENTIALS: RequestCredentials = 'same-origin'
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}
async function checked(response: Response) {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      detail = Array.isArray(body.detail)
        ? body.detail.map((e: any) => `${(e.loc ?? []).slice(1).join('.')}: ${e.msg}`).join('; ')
        : typeof body.detail === 'string'
          ? body.detail
          : detail
    } catch {}
    throw new ApiError(response.status, detail)
  }
  return response
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await checked(await fetch(`${BASE}${path}`, { ...init, credentials: CREDENTIALS }))
  return r.json() as Promise<T>
}
export const get = <T = any>(path: string) => request<T>(path)
// Descarga binaria por GET (p. ej. exportar un proyecto); mismo manejo de
// errores que get().
export async function getBlob(path: string): Promise<Blob> {
  const r = await checked(await fetch(`${BASE}${path}`, { credentials: CREDENTIALS }))
  return r.blob()
}
export const post = <T = any>(path: string, body: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
export const put = <T = any>(path: string, body: unknown) =>
  request<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
// Sin cuerpo de respuesta (204): no pasa por request/checked porque no hay
// JSON que interpretar.
export const del = async (path: string): Promise<void> => {
  await checked(await fetch(`${BASE}${path}`, { method: 'DELETE', credentials: CREDENTIALS }))
}
// Devuelve el cuerpo sin interpretarlo como JSON, para los endpoints que
// responden con un archivo. Lo usa el informe del espectro, que viaja como ZIP
// con el JSON y el PNG del gráfico dentro.
export async function postForBlob(path: string, body: unknown): Promise<Blob> {
  const r = await checked(
    await fetch(`${BASE}${path}`, {
      method: 'POST',
      credentials: CREDENTIALS,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
  return r.blob()
}
export async function upload<T = any>(path: string, file: File, method = 'POST') {
  const data = new FormData()
  data.append('file', file)
  return request<T>(path, { method, body: data })
}
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export async function download(path: string, body: unknown | undefined, filename: string) {
  const r = await checked(
    await fetch(`${BASE}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: CREDENTIALS,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  )
  saveBlob(await r.blob(), filename)
}
