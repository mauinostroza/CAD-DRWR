// Cliente único del puente SAP2000, usado por SapPage.tsx, PerfilesPage.tsx y
// esbelteces/EsbeltecesPage.tsx. Sustituye al cliente duplicado que cada
// pantalla mantenía por su cuenta.
//
// El puente vive en una dirección distinta (típicamente http://127.0.0.1:8765)
// y nunca pasa por el backend propio de la aplicación. El backend propio sólo
// interviene para exponer, en modo local, las credenciales que el puente dejó
// escritas en disco (ver GET /api/sap/local-credentials más abajo).
import { ApiError, get, postForBlob } from './lib_client'

export type BridgeCreds =
  | { source: 'local'; url: string; token: string }
  | { source: 'paired'; url: string; token: string }
  | { source: 'none' }

const PAIRING_KEY = 'sap_bridge_pairing'

type StoredPairing = { url: string; token: string }

// El emparejamiento guardado nunca debe romper la página: si localStorage no
// está disponible (ventana privada, permisos del sitio) o el contenido está
// corrupto, se comporta como si no hubiera nada guardado.
export function loadStoredPairing(): StoredPairing | null {
  try {
    const raw = localStorage.getItem(PAIRING_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (typeof parsed?.url === 'string' && typeof parsed?.token === 'string') return parsed
    return null
  } catch {
    return null
  }
}

export function saveStoredPairing(url: string, token: string): void {
  try {
    localStorage.setItem(PAIRING_KEY, JSON.stringify({ url, token }))
  } catch {
    // Si no se puede guardar, el usuario simplemente vuelve a emparejar en la
    // próxima visita: no es un error que deba interrumpir el flujo.
  }
}

export function clearStoredPairing(): void {
  try {
    localStorage.removeItem(PAIRING_KEY)
  } catch {
    // Nada que hacer si localStorage no responde: no hay nada persistente que
    // limpiar desde el punto de vista de la página.
  }
}

// Misma validación que ya usaban SapPage.tsx y EsbeltecesPage.tsx: sólo HTTP
// en localhost/127.0.0.1/[::1]. El puente jamás debe llamarse por HTTPS ni por
// un host remoto.
export function assertLocalUrl(url: string): void {
  const base = new URL(url)
  if (base.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(base.hostname))
    throw new Error('Use la dirección local del puente (HTTP en localhost o 127.0.0.1).')
}

// Intenta primero el modo local (el puente ya arrancado en este mismo equipo,
// vía B del plan); si no está disponible, cae al emparejamiento guardado en
// localStorage; si tampoco hay nada, no hay credenciales.
export async function getBridgeCredentials(): Promise<BridgeCreds> {
  try {
    const data = await get<{ available: boolean; url?: string; token?: string }>('/sap/local-credentials')
    if (data.available && data.url && data.token) return { source: 'local', url: data.url, token: data.token }
  } catch {
    // 404 en modo servidor, o un fallo de red: en ambos casos se sigue al
    // emparejamiento guardado, sin propagar el error.
  }
  const stored = loadStoredPairing()
  if (stored) return { source: 'paired', url: stored.url, token: stored.token }
  return { source: 'none' }
}

// Defensa barata contra la fuga del token (S-07): el token nunca se escribe en
// la consola ni viaja dentro de un mensaje de error. Si el puente (o un proxy)
// devolviera el token en su "detail", se enmascara antes de lanzar el error.
function bridgeErrorMessage(detail: unknown, creds: BridgeCreds): string {
  let msg = typeof detail === 'string' ? detail : JSON.stringify(detail ?? '')
  if (creds.source !== 'none' && creds.token) msg = msg.split(creds.token).join('[token]')
  return msg
}

// 401 con credenciales emparejadas: el token venció, fue revocado o el puente
// se reinstaló. Se limpia lo guardado y el mensaje invita a volver a conectar.
const RECONNECT_HINT = 'Vuelva a conectar el puente.'
function unauthorizedMessage(detail: unknown, creds: BridgeCreds): string {
  const msg = bridgeErrorMessage(detail, creds)
  if (creds.source !== 'paired') return msg
  if (/vuelva a conectar/i.test(msg)) return msg
  return `${msg} ${RECONNECT_HINT}`
}

// Llamada directa al puente (nunca al backend propio). Traduce el "detail"
// del puente a un mensaje de error concreto, igual que hacía cada pantalla
// por su cuenta. Un 401 con credenciales emparejadas limpia lo guardado: el
// emparejamiento ya no vale, fue revocado o el puente se reinstaló.
export async function sapRequest(
  creds: BridgeCreds,
  path: string,
  body?: any,
  signal?: AbortSignal,
): Promise<any> {
  if (creds.source === 'none') throw new Error('El puente SAP2000 no está emparejado todavía.')
  assertLocalUrl(creds.url)
  const r = await fetch(creds.url.replace(/\/$/, '') + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      Authorization: `Bearer ${creds.token}`,
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })
  const data = await r.json()
  if (!r.ok) {
    const detail = data.detail ?? data
    if (r.status === 401) {
      if (creds.source === 'paired') clearStoredPairing()
      throw new Error(unauthorizedMessage(detail, creds))
    }
    throw new Error(bridgeErrorMessage(detail, creds))
  }
  return data
}

// "Desconectar": revoca en el puente el token emparejado con el que se estaba
// trabajando (POST /v1/sap/revoke) y borra el guardado local. Es de mejor
// esfuerzo: si el puente no responde, o es un agente anterior sin esta ruta
// (404), igualmente se limpia localStorage. Con credenciales locales (token de
// arranque) no hay nada que revocar ni guardar: no hace nada.
export async function revokeBridgeToken(creds: BridgeCreds): Promise<void> {
  if (creds.source !== 'paired') return
  try {
    assertLocalUrl(creds.url)
    await fetch(creds.url.replace(/\/$/, '') + '/v1/sap/revoke', {
      method: 'POST',
      headers: { Authorization: `Bearer ${creds.token}` },
    })
  } catch {
    // Sin respuesta del puente: se limpia igual abajo.
  }
  clearStoredPairing()
}

// Igual que `sapRequest`, pero sin lanzar en respuestas no-ok: devuelve
// siempre {status, data}. Lo usa PerfilesPage.tsx para distinguir un 409 con
// `detail.code === 'section_exists'` (que exige preguntar antes de
// sobrescribir) de cualquier otro error, algo que `sapRequest` no permite
// porque descarta el código de estado al lanzar el error genérico.
export async function sapRequestRaw(
  creds: BridgeCreds,
  path: string,
  body?: any,
): Promise<{ status: number; data: any }> {
  if (creds.source === 'none') throw new Error('El puente SAP2000 no está emparejado todavía.')
  assertLocalUrl(creds.url)
  const r = await fetch(creds.url.replace(/\/$/, '') + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      Authorization: `Bearer ${creds.token}`,
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await r.json()
  if (r.status === 401 && creds.source === 'paired') {
    clearStoredPairing()
    data.detail = unauthorizedMessage(data.detail ?? data, creds)
  }
  return { status: r.status, data }
}

// Arranca un emparejamiento de un clic contra el puente indicado (modo
// servidor remoto, ver sección C del plan). Sin token todavía: es la ruta que
// entrega el primero.
export async function startPairing(
  bridgeUrl: string,
): Promise<{ requestId: string; expiresIn: number; confirmCode: string }> {
  assertLocalUrl(bridgeUrl)
  const r = await fetch(bridgeUrl.replace(/\/$/, '') + '/v1/sap/pairing/request', { method: 'POST' })
  const data = await r.json()
  if (!r.ok)
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data))
  return { requestId: data.request_id, expiresIn: data.expires_in, confirmCode: data.confirm_code }
}

export async function pollPairing(
  bridgeUrl: string,
  requestId: string,
): Promise<{ status: 'pending' | 'approved' | 'denied' | 'expired'; secret?: string; url?: string }> {
  assertLocalUrl(bridgeUrl)
  const r = await fetch(bridgeUrl.replace(/\/$/, '') + `/v1/sap/pairing/poll/${requestId}`)
  const data = await r.json()
  if (!r.ok)
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data))
  return data
}

// Reexportado para que las pruebas puedan distinguir "modo servidor" (404) de
// un fallo de red real sin importar directamente de lib_client.
export { ApiError }

// ---------------------------------------------------------------------------
// Rutas nuevas del puente para Fundaciones (bridge/actions.py, fase F1, en
// paralelo). Contrato fijado en el plan — ver "Rutas nuevas del puente".
// ---------------------------------------------------------------------------
import type { FoundationDataset, FoundationGroup } from './foundations/api'

export type ForcesFoundations = { f1: number; f2: number; f3: number; m1: number; m2: number; m3: number }
export type LoadRow = { joint: string; load_pat: string; coord_sys: string } & ForcesFoundations
export type LoadChange = {
  joint: string
  load_pat: string
  before: ForcesFoundations | null
  after: ForcesFoundations
}

// `envolventes` (Diagramas de shells): subconjunto de `combos` de tipo
// Envelope (RespCombo.ComboType == 1); `[]` si el puente no pudo determinarlo.
export function getFoundationsCases(
  creds: BridgeCreds,
): Promise<{ load_cases: string[]; combos: string[]; envolventes: string[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/cases')
}

export function getFoundationsSelection(
  creds: BridgeCreds,
  kind: 'joints' | 'shells' | 'frames',
): Promise<{ kind: string; names: string[] }> {
  return sapRequest(creds, `/v1/sap/actions/foundations/selection?kind=${kind}`)
}

export function getFoundationsGroups(creds: BridgeCreds): Promise<{ groups: FoundationGroup[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/groups')
}

export function getFoundationsLoadPatterns(creds: BridgeCreds): Promise<{ load_patterns: string[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/load-patterns')
}

export function getFoundationsExistingLoads(
  creds: BridgeCreds,
  joints: string[],
): Promise<{ rows: LoadRow[] }> {
  return sapRequest(
    creds,
    `/v1/sap/actions/foundations/loads/existing?joints=${encodeURIComponent(joints.join(','))}`,
  )
}

export function previewFoundationsLoads(
  creds: BridgeCreds,
  rows: LoadRow[],
  mode: 'replace' | 'add',
): Promise<{ changes: LoadChange[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/loads/preview', { rows, mode })
}

export function applyFoundationsLoads(
  creds: BridgeCreds,
  rows: LoadRow[],
  mode: 'replace' | 'add',
): Promise<{ applied: number; failed: string[]; missing_joints: string[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/loads/apply', { rows, mode, confirmed: true })
}

export function snapshotFoundations(
  creds: BridgeCreds,
  filtro?: { joints?: string[]; shells?: string[]; cases?: string[]; combos?: string[] },
): Promise<FoundationDataset> {
  return sapRequest(creds, '/v1/sap/snapshot', filtro ?? {})
}

// Geometría de malla + resultados de presión de suelo de un conjunto de
// shells para una combinación — insumo de "Generar información de
// exportación..." (DialogoExportacion.tsx) para las imágenes de diagrama de
// Presión de contacto. Puerto del contrato de
// app/sap2000/diagramas_shell.py::obtener_geometria_shells/
// obtener_resultados_shell; la respuesta se reenvía verbatim al backend
// propio (POST /foundations/export/bundle), que la usa para dibujar el PNG.
export type FoundationsShellDiagram = { elementos: unknown; joints: unknown; resultados: unknown }

export function getFoundationsShellDiagram(
  creds: BridgeCreds,
  body: { shells: string[]; combinacion: string },
): Promise<FoundationsShellDiagram> {
  return sapRequest(creds, '/v1/sap/actions/foundations/shell-diagram', body)
}

// === Diseño de secciones (section cuts) — bridge/foundations_cuts.py ========
export type SectionCutDef = { nombre: string; grupo: string }
export type SectionCutCreateBody = {
  nombre: string
  grupo?: string
  frames?: string[]
  desbloquear?: boolean
}
export type SectionCutCreateResult = {
  creado: boolean
  requiere_desbloqueo: boolean
  mensaje: string
  elementos: string[]
}
export type SectionCutForceRow = {
  caso: string
  P: number
  V2: number
  V3: number
  M2: number
  M3: number
  T: number
}
export type SectionCutForcesResult = {
  resultados: Record<string, SectionCutForceRow[]>
  model_locked: boolean
}

// Section cuts ya definidos en el modelo conectado (tabla "Section Cut Definitions").
export function listFoundationsSectionCuts(creds: BridgeCreds): Promise<{ cuts: SectionCutDef[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/section-cuts')
}

// Nombres de TODOS los grupos del modelo (incluidos los que solo tienen frames).
export function listFoundationsSectionCutGroups(creds: BridgeCreds): Promise<{ groups: string[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/section-cuts/groups')
}

// Simulación: no modifica SAP2000; informa si habría que desbloquear el modelo.
export function previewFoundationsSectionCut(
  creds: BridgeCreds,
  body: SectionCutCreateBody,
): Promise<SectionCutCreateResult> {
  return sapRequest(creds, '/v1/sap/actions/foundations/section-cuts/preview', body)
}

// Crea el section cut (confirmed:true obligatorio en el puente). Con el modelo
// bloqueado y desbloquear falso no hace nada y devuelve requiere_desbloqueo.
export function applyFoundationsSectionCut(
  creds: BridgeCreds,
  body: SectionCutCreateBody,
): Promise<SectionCutCreateResult> {
  return sapRequest(creds, '/v1/sap/actions/foundations/section-cuts/apply', { ...body, confirmed: true })
}

// Error de extracción con el indicador "modelo no corrido" del puente.
export class SectionCutForcesError extends Error {
  modelNotRun: boolean
  constructor(message: string, modelNotRun: boolean) {
    super(message)
    this.name = 'SectionCutForcesError'
    this.modelNotRun = modelNotRun
  }
}

export async function extractFoundationsSectionCutForces(
  creds: BridgeCreds,
  cuts: string[],
  combos: string[],
): Promise<SectionCutForcesResult> {
  const { status, data } = await sapRequestRaw(creds, '/v1/sap/actions/foundations/section-cuts/forces', {
    cuts,
    combos,
  })
  if (status >= 200 && status < 300) return data
  const detail = data?.detail
  if (detail && typeof detail === 'object' && typeof detail.message === 'string')
    throw new SectionCutForcesError(detail.message, detail.model_not_run === true)
  throw new SectionCutForcesError(typeof detail === 'string' ? detail : JSON.stringify(detail ?? data), false)
}
// === Fin Diseño de secciones ================================================

// === Diagramas de shells (Beta) — puente: shell-results / shell-results-multi /
// pedestal-candidates (bridge/foundations_shells.py). Contrato exacto en
// docs/SAP_ACTIONS.md ("Diagramas de shells (port del escritorio)") y en
// bridge_contracts.json. ===
export type ShellTipoSalida = 'forces' | 'stresses' | 'soil_pressure'
export type ShellPaso = 'max' | 'min'

// Componentes por tipo de salida (diagramas_shell.COMPONENTES_*).
export const SHELL_COMPONENTES_FORCES = ['F11', 'F22', 'F12', 'M11', 'M22', 'M12', 'V13', 'V23'] as const
export const SHELL_COMPONENTES_STRESSES = ['S11', 'S22', 'S12', 'SMax', 'SMin', 'SVM', 'T13', 'T23'] as const
export const SHELL_COMPONENTES_SOIL_PRESSURE = ['Pressure'] as const

export type ShellResultsRequest = {
  shells: string[]
  // Nombre REAL de la combinación/caso (sin el sufijo " [max]"/" [min]").
  combinacion: string
  tipo: ShellTipoSalida
  // forces/stresses: uno de SHELL_COMPONENTES_*; soil_pressure: se ignora ('Pressure').
  componente: string
  // Solo forces/stresses (envolventes). soil_pressure lo ignora.
  paso?: ShellPaso | null
  // true: elementos/joints/joints_z vuelven vacíos ({}) — para refrescar solo
  // resultados cuando la geometría ya está en caché en la web.
  sin_geometria?: boolean
}

export type ShellResultsResponse = {
  // {elemento_malla: [p1, p2, p3, p4]} (p4 = p3 si es triangular)
  elementos: Record<string, [string, string, string, string]>
  // {punto: [x, y]}
  joints: Record<string, [number, number]>
  // {punto: z}
  joints_z: Record<string, number>
  // {elemento_malla: {punto: valor}}; vacío si no hay resultados
  resultados: Record<string, Record<string, number>>
  // Texto literal del escritorio (mensaje_sin_resultados); '' si hay resultados
  mensaje_sin_resultados: string
}

export function getFoundationsShellResults(
  creds: BridgeCreds,
  body: ShellResultsRequest,
  signal?: AbortSignal,
): Promise<ShellResultsResponse> {
  return sapRequest(creds, '/v1/sap/actions/foundations/shell-results', body, signal)
}

export type ShellFranjaRequest = {
  centro_x: number
  centro_y: number
  largo: number
  ancho: number
  largo_en_x: boolean
}

export type ShellComboRef = { combinacion: string; paso?: ShellPaso | null }

export type ShellResultsMultiRequest = {
  shells: string[]
  // Una entrada por combinación; las envolventes van como dos entradas
  // ({combinacion:'ENV', paso:'max'} y {…, paso:'min'}). Para mostrar
  // progreso/cancelar, llamar una vez por combinación (o por lotes chicos).
  combos: ShellComboRef[]
  tipo: ShellTipoSalida
  // Por defecto, todos los de `tipo`.
  componentes?: string[]
  // Franjas visibles (1..200); el índice de la respuesta es la posición aquí.
  franjas: ShellFranjaRequest[]
}

export type ShellResultsMultiFila = {
  // Índice en `franjas` de la petición
  franja: number
  combinacion: string
  paso: ShellPaso | null
  // {componente: extremo gobernante}; sin la clave si no hubo estaciones
  valores: Record<string, number>
}

export type ShellResultsMultiResponse = {
  // Una fila por franja × combo (con `valores` {} si la combinación no trajo datos)
  filas: ShellResultsMultiFila[]
  // Combos cuya lectura falló (no tienen filas)
  errores: { combinacion: string; paso: ShellPaso | null; error: string }[]
}

export function getFoundationsShellResultsMulti(
  creds: BridgeCreds,
  body: ShellResultsMultiRequest,
  signal?: AbortSignal,
): Promise<ShellResultsMultiResponse> {
  return sapRequest(creds, '/v1/sap/actions/foundations/shell-results-multi', body, signal)
}

export type PedestalCandidato = {
  frame: string
  largo: number
  ancho: number
  largo_en_x: boolean
  centro_x: number
  centro_y: number
  aproximado: boolean
  // '' si no es aproximado; textos literales del escritorio
  motivo_aviso: string
}

export function getFoundationsPedestalCandidates(
  creds: BridgeCreds,
  joints: string[],
  signal?: AbortSignal,
): Promise<{ candidatos: PedestalCandidato[] }> {
  return sapRequest(creds, '/v1/sap/actions/foundations/pedestal-candidates', { joints }, signal)
}
// "Exportar imagen..." — backend propio (NO el puente): POST /foundations/diagram/shell.png
// con dibujar_diagrama_shell (200 dpi, sin franjas/pedestales). Nombre sugerido
// de descarga: "diagrama_shell.png". 422 si no hay elementos dibujables.
export type ShellPngRequest = {
  elementos: ShellResultsResponse['elementos']
  joints: ShellResultsResponse['joints']
  resultados: ShellResultsResponse['resultados']
  componente: string
  // Combinación mostrada en el título (p. ej. 'ENV [max]')
  caso: string
  // 'Promedio en nodos (contornos)' (por defecto) | 'Promedio por elemento (sólido)' | 'Sin promediar (por elemento)'
  metodo?: string
  unidad?: string
  escalonado?: boolean
  // [mínimo, máximo] manuales; ignorados si mínimo >= máximo
  limites?: [number, number] | null
}

export function exportFoundationsShellPng(body: ShellPngRequest): Promise<Blob> {
  return postForBlob('/foundations/diagram/shell.png', body)
}
// === Fin Diagramas de shells ================================================
