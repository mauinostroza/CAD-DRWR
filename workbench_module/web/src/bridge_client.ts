// STUB del arnés: imita las firmas de web/src/bridge_client.ts del workbench (NO se copia).
// Solo lo importa bridgeCad.ts.

export type BridgeCreds =
  | { source: 'local' | 'paired'; url: string; token: string }
  | { source: 'none' }

export type RespuestaCruda<T> = { status: number; data: T }

export async function getBridgeCredentials(): Promise<BridgeCreds> {
  return { source: 'none' }
}

export async function sapRequestRaw<T = unknown>(
  creds: BridgeCreds,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<RespuestaCruda<T>> {
  if (creds.source === 'none') throw new TypeError('Sin credenciales del puente')
  const res = await fetch(creds.url + path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${creds.token}`,
    },
    body: body === undefined ? '{}' : JSON.stringify(body),
    signal,
  })
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  return { status: res.status, data: data as T }
}

export async function sapRequest<T>(
  creds: BridgeCreds,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const r = await sapRequestRaw<unknown>(creds, path, body, signal)
  if (r.status >= 200 && r.status < 300) return r.data as T
  const detalle = (r.data as { detail?: unknown } | null)?.detail
  throw new Error(typeof detalle === 'string' ? detalle : `Error ${r.status}`)
}
