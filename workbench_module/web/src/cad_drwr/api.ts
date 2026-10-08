import { get, post, postForBlob, ApiError } from '../lib_client'
import type { DibujoJson, EstadoModulo, Lamina, ModuloInfo, Params } from './tipos'

const RAIZ = '/cad_drwr'

async function llamar<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn()
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 401) throw new Error('Inicie sesión para continuar.')
      if (e.status === 503)
        throw new Error(`El módulo CAD-DRWR no está disponible en el servidor: ${e.message}`)
    }
    throw e
  }
}

export const estadoModulo = (signal?: AbortSignal) =>
  llamar(() => get<EstadoModulo & { dxf: boolean }>(`${RAIZ}/estado`, signal))

export const listarModulos = (signal?: AbortSignal) =>
  llamar(() => get<ModuloInfo[]>(`${RAIZ}/modulos`, signal))

export type DibujoRespuesta = DibujoJson & { modulo: string; hash: string; solapes: string[][] }

export const pedirDibujo = (
  modulo: string,
  params: Params,
  lamina?: Lamina,
  signal?: AbortSignal,
) => llamar(() => post<DibujoRespuesta>(`${RAIZ}/dibujo`, { modulo, params, lamina }, signal))

export const descargarDxf = (modulo: string, params: Params, lamina?: Lamina) =>
  llamar(() => postForBlob(`${RAIZ}/dxf`, { modulo, params, lamina }))

export const descargarLote = (items: { modulo: string; params: Params }[], lamina?: Lamina) =>
  llamar(() => postForBlob(`${RAIZ}/dxf-lote`, { items, lamina }))
