// Edición pura (sin red) de la geometría de fundación SAP2000 (FundacionGeom.to_dict()).
// Todas las funciones devuelven copias nuevas; nunca se modifica la geometría recibida
// y el contorno de cada zapata se conserva tal cual.

export type PedestalGeom = {
  frame: string
  largo: number
  ancho: number
  largo_en_x: boolean
  centro: [number, number]
  punto_pie: string
  aproximado: boolean
  motivo_aviso: string
}

export type AreaGeom = {
  nombre: string
  seccion: string
  espesor: number | null
  pts_nombres: string[]
  pts: [number, number, number][]
  pts_malla: string[]
}

export type ZapataGeom = {
  nombre: string
  areas: AreaGeom[]
  contorno: [number, number][]
  pedestales: PedestalGeom[]
}

export type FundacionGeom = {
  nombre: string
  zapatas: ZapataGeom[]
}

export type ResumenGeom = { zapatas: number; pedestales: number; areas: number }

export type CambiosPedestal = Partial<Pick<PedestalGeom, 'largo' | 'ancho' | 'largo_en_x'>>

function valorPositivo(v: number): boolean {
  return typeof v === 'number' && Number.isFinite(v) && v > 0
}

/** Cambia la zapata i (si existe) con `fn`; el resto de zapatas se copia tal cual. */
function conZapata(geom: FundacionGeom, i: number, fn: (z: ZapataGeom) => ZapataGeom): FundacionGeom {
  return {
    ...geom,
    zapatas: geom.zapatas.map((z, k) => (k === i ? fn(z) : z)),
  }
}

export function resumenGeom(geom: FundacionGeom): ResumenGeom {
  return {
    zapatas: geom.zapatas.length,
    pedestales: geom.zapatas.reduce((n, z) => n + z.pedestales.length, 0),
    areas: geom.zapatas.reduce((n, z) => n + z.areas.length, 0),
  }
}

/** Fija el espesor (mm) de todas las áreas de la zapata i. Valores no válidos no cambian nada. */
export function setEspesorZapata(geom: FundacionGeom, i: number, mm: number): FundacionGeom {
  if (!valorPositivo(mm)) return { ...geom, zapatas: [...geom.zapatas] }
  return conZapata(geom, i, z => ({
    ...z,
    areas: z.areas.map(a => ({ ...a, espesor: mm })),
  }))
}

/**
 * Cambia largo, ancho u orientación del pedestal j de la zapata i.
 * Largo y ancho sólo se aplican si son finitos y mayores que 0.
 */
export function setPedestal(
  geom: FundacionGeom,
  i: number,
  j: number,
  cambios: CambiosPedestal,
): FundacionGeom {
  const aplicar: CambiosPedestal = {}
  if (cambios.largo !== undefined && valorPositivo(cambios.largo)) aplicar.largo = cambios.largo
  if (cambios.ancho !== undefined && valorPositivo(cambios.ancho)) aplicar.ancho = cambios.ancho
  if (cambios.largo_en_x !== undefined) aplicar.largo_en_x = cambios.largo_en_x
  return conZapata(geom, i, z => ({
    ...z,
    pedestales: z.pedestales.map((p, k) => (k === j ? { ...p, ...aplicar } : p)),
  }))
}

/** Quita el pedestal j de la zapata i. */
export function quitarPedestal(geom: FundacionGeom, i: number, j: number): FundacionGeom {
  return conZapata(geom, i, z => ({
    ...z,
    pedestales: z.pedestales.filter((_, k) => k !== j),
  }))
}

/** Devuelve una geometría sólo con las zapatas de los índices indicados (orden original). */
export function incluirZapata(geom: FundacionGeom, indicesIncluidos: readonly number[]): FundacionGeom {
  const incluir = new Set(indicesIncluidos)
  return {
    ...geom,
    zapatas: geom.zapatas.filter((_, i) => incluir.has(i)),
  }
}

function esObjeto(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

function esZapataValida(z: unknown): boolean {
  return (
    esObjeto(z) &&
    typeof z.nombre === 'string' &&
    Array.isArray(z.areas) &&
    Array.isArray(z.contorno) &&
    Array.isArray(z.pedestales)
  )
}

/** Comprobación ligera de forma: nombre, zapatas, áreas, contorno y pedestales. */
export function esGeomValida(x: unknown): x is FundacionGeom {
  if (!esObjeto(x) || typeof x.nombre !== 'string' || !Array.isArray(x.zapatas)) return false
  return x.zapatas.every(esZapataValida)
}
