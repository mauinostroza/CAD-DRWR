// Cliente del puente local (ZWCAD/AutoCAD y SAP2000) para CAD-DRWR.
// Único archivo del módulo que importa ../bridge_client.

import { getBridgeCredentials, sapRequestRaw, type BridgeCreds } from '../bridge_client'
import type { DibujoRespuesta } from './api'
import type { EntCad } from './tipos'

export type { BridgeCreds }

const PREFIJO = '/v1/sap/actions/cad'

export const MENSAJE_ANTIGUO ='Su SAP2000Bridge es anterior a este módulo; actualice el puente.'
export const MENSAJE_SESION =
  'El puente rechazó el token. Vuelva a emparejar SAP2000Bridge desde el módulo SAP2000 del Workbench.'
export const MENSAJE_SIN_EMPAREJAR =
  'No hay un puente emparejado. Abra SAP2000Bridge y use el emparejamiento del módulo SAP2000 del Workbench.'

/** Tamaño de cada lote de entidades enviado a /draw/batch. */
export const TAM_LOTE = 500

export type CodigoError = 'sin_puente' | 'sesion' | 'antiguo' | 'cad' | 'validacion' | 'otro'

export class ErrorPuente extends Error {
  readonly codigo: CodigoError
  readonly estado: number | null

  constructor(codigo: CodigoError, mensaje: string, estado: number | null = null) {
    super(mensaje)
    this.name = 'ErrorPuente'
    this.codigo = codigo
    this.estado = estado
  }
}

/** Credenciales actuales del puente (emparejamiento del Workbench o puente local). */
export const obtenerCredenciales = (): Promise<BridgeCreds> => getBridgeCredentials()

// ------------------------------------------------------------ errores --

function esAbort(e: unknown): boolean {
  return (e as { name?: unknown } | null)?.name === 'AbortError'
}

function abortar(): DOMException {
  return new DOMException('Operación cancelada', 'AbortError')
}

function lanzarSiAborta(signal?: AbortSignal): void {
  if (signal?.aborted) throw abortar()
}

/** Extrae el texto que devuelve el servidor (detail string o lista de errores FastAPI). */
export function textoDetalle(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null
  const detalle = (data as { detail?: unknown }).detail
  if (typeof detalle === 'string') return detalle.trim() || null
  if (Array.isArray(detalle)) {
    const partes: string[] = []
    for (const item of detalle) {
      if (!item || typeof item !== 'object') continue
      const { loc, msg } = item as { loc?: unknown; msg?: unknown }
      if (typeof msg !== 'string') continue
      const campo = Array.isArray(loc) ? loc.filter(p => p !== 'body').join('.') : ''
      partes.push(campo ? `${campo}: ${msg}` : msg)
    }
    return partes.length > 0 ? partes.join('; ') : null
  }
  return null
}

function errorDeRespuesta(status: number, data: unknown): ErrorPuente {
  const texto = textoDetalle(data)
  if (status === 401) return new ErrorPuente('sesion', MENSAJE_SESION, status)
  if (status === 404) return new ErrorPuente('antiguo', MENSAJE_ANTIGUO, status)
  if (status === 409)
    return new ErrorPuente('cad', texto ?? 'El CAD no pudo completar la operación.', status)
  if (status === 422)
    return new ErrorPuente('validacion', texto ?? 'El puente rechazó los datos enviados.', status)
  return new ErrorPuente('otro', texto ?? `El puente respondió con error ${status}.`, status)
}

// ------------------------------------------------------------ llamada --

async function llamar<T>(
  creds: BridgeCreds,
  ruta: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  if (creds.source === 'none') throw new ErrorPuente('sin_puente', MENSAJE_SIN_EMPAREJAR)
  const res = await sapRequestRaw<unknown>(creds, PREFIJO + ruta, body, signal).catch(
    (e: unknown) => {
      if (esAbort(e)) throw e
      throw new ErrorPuente(
        'sin_puente',
        `No se pudo contactar con SAP2000Bridge en ${creds.url}. Compruebe que la aplicación esté abierta.`,
      )
    },
  )
  if (res.status >= 200 && res.status < 300) return res.data as T
  throw errorDeRespuesta(res.status, res.data)
}

// -------------------------------------------------------- rutas CAD --

export type EstadoCad = {
  conectado: boolean
  programa: string | null
  version: string | null
  documento: string | null
  detalle: string
}

export type ErrorEntidad = { indice: number; tipo: string; motivo: string }

export type SesionCad = { sesion: string; programa: string; documento: string | null }

export type ResultadoLote = { creadas: number; omitidas: number; errores: ErrorEntidad[] }

export type ResultadoFin = {
  documento: string | null
  creadas: number
  omitidas: number
  resumen: string
}

export type PuntoClic = { x: number; y: number }

export const estadoCad = (creds: BridgeCreds, signal?: AbortSignal) =>
  llamar<EstadoCad>(creds, '/status', {}, signal)

export const pickCad = (
  creds: BridgeCreds,
  body: { mensaje?: string; timeout_s?: number } = {},
  signal?: AbortSignal,
) => llamar<PuntoClic>(creds, '/pick', body, signal)

export const beginCad = (
  creds: BridgeCreds,
  body: { confirmed: true; origen?: [number, number]; n_total: number; th: number },
  signal?: AbortSignal,
) => llamar<SesionCad>(creds, '/draw/begin', body, signal)

export const batchCad = (
  creds: BridgeCreds,
  body: { sesion: string; ents: EntCad[] },
  signal?: AbortSignal,
) => llamar<ResultadoLote>(creds, '/draw/batch', body, signal)

export const endCad = (creds: BridgeCreds, sesion: string, signal?: AbortSignal) =>
  llamar<ResultadoFin>(creds, '/draw/end', { sesion }, signal)

// ------------------------------------------------------- rutas SAP --

export type GrupoSap = { nombre: string; n_shells: number }

export type EstadoJob = 'en_curso' | 'listo' | 'error' | 'cancelado'

export type EstadoFundacion = {
  estado: EstadoJob
  etapa: string
  hechas: number
  total: number
  transcurrido_s: number
  resultado?: unknown
  error?: string | null
}

export const gruposSap = (creds: BridgeCreds, signal?: AbortSignal) =>
  llamar<{ grupos: GrupoSap[] }>(creds, '/sap/groups', {}, signal)

export const iniciarFundacion = (creds: BridgeCreds, grupo: string, signal?: AbortSignal) =>
  llamar<{ job: string }>(creds, '/sap/foundation/start', { grupo }, signal)

export const estadoFundacion = (creds: BridgeCreds, job: string, signal?: AbortSignal) =>
  llamar<EstadoFundacion>(creds, '/sap/foundation/status', { job }, signal)

export const cancelarFundacion = (creds: BridgeCreds, job: string, signal?: AbortSignal) =>
  llamar<{ cancelado: boolean }>(creds, '/sap/foundation/cancel', { job }, signal)

// ------------------------------------------------------ envío de dibujo --

export type FaseEnvio = 'conectando' | 'esperando_clic' | 'enviando' | 'finalizando' | 'listo'

export type EstadoEnvio = {
  fase: FaseEnvio
  hechas: number
  total: number
  mensaje: string
}

export type ResumenEnvio = {
  programa: string
  documento: string | null
  creadas: number
  omitidas: number
  resumen: string
  /** Errores de todos los lotes; índice global (0 = primera entidad de dibujo.cad). */
  errores: ErrorEntidad[]
}

export type OpcionesEnvio = {
  ubicarConClic: boolean
  onEstado?: (estado: EstadoEnvio) => void
  signal?: AbortSignal
}

/**
 * Envía el dibujo al CAD: status -> (pick) -> begin -> batches de TAM_LOTE -> end.
 * Si se cancela o falla después de begin, llama a end para liberar la sesión.
 */
export async function enviarDibujo(
  creds: BridgeCreds,
  dibujo: DibujoRespuesta,
  opciones: OpcionesEnvio,
): Promise<ResumenEnvio> {
  const { ubicarConClic, onEstado, signal } = opciones
  const total = dibujo.cad.length
  const emitir = (fase: FaseEnvio, hechas: number, mensaje: string) =>
    onEstado?.({ fase, hechas, total, mensaje })

  emitir('conectando', 0, 'Comprobando el puente y el CAD…')
  const estado = await estadoCad(creds, signal)
  if (!estado.conectado) {
    throw new ErrorPuente('cad', estado.detalle || 'No hay ZWCAD/AutoCAD abierto.')
  }

  let origen: [number, number] | undefined
  if (ubicarConClic) {
    lanzarSiAborta(signal)
    emitir(
      'esperando_clic',
      0,
      'Haga clic en la ventana de ZWCAD/AutoCAD para indicar el punto de inserción (Esc en el CAD cancela).',
    )
    const punto = await pickCad(
      creds,
      { mensaje: 'Indique el punto de inserción del dibujo', timeout_s: 120 },
      signal,
    )
    origen = [punto.x, punto.y]
  }

  lanzarSiAborta(signal)
  emitir('enviando', 0, 'Abriendo la sesión de dibujo…')
  const sesion = await beginCad(
    creds,
    { confirmed: true, origen, n_total: total, th: dibujo.th },
    signal,
  )

  const errores: ErrorEntidad[] = []
  let liberada = false
  try {
    let hechas = 0
    for (let i = 0; i < total; i += TAM_LOTE) {
      lanzarSiAborta(signal)
      const lote = dibujo.cad.slice(i, i + TAM_LOTE)
      const r = await batchCad(creds, { sesion: sesion.sesion, ents: lote }, signal)
      for (const e of r.errores) {
        errores.push({ indice: e.indice + i, tipo: e.tipo, motivo: e.motivo })
      }
      hechas += lote.length
      emitir('enviando', hechas, `Enviadas ${hechas} de ${total} entidades.`)
    }

    emitir('finalizando', hechas, 'Regenerando el CAD y liberando la sesión…')
    liberada = true
    const fin = await endCad(creds, sesion.sesion)
    emitir('listo', total, 'Dibujo enviado.')
    return {
      programa: sesion.programa,
      documento: fin.documento,
      creadas: fin.creadas,
      omitidas: fin.omitidas,
      resumen: fin.resumen,
      errores,
    }
  } catch (e) {
    if (!liberada) {
      // Mejor esfuerzo: si la sesión ya no existe, el puente la libera por TTL.
      await endCad(creds, sesion.sesion).catch(() => undefined)
    }
    throw e
  }
}
