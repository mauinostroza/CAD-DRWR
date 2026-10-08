// STUB del arnés: imita las firmas de web/src/lib_client.ts del workbench (NO se copia).
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}
const BASE = '/api'
async function checked(res: Response): Promise<Response> {
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* sin cuerpo */
    }
    throw new ApiError(res.status, msg)
  }
  return res
}
export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await checked(await fetch(BASE + path, { credentials: 'same-origin', signal }))).json()
}
export async function post<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })
  return (await checked(res)).json()
}
export async function postForBlob(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<Blob> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })
  return (await checked(res)).blob()
}
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
