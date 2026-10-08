// Colores, anchos y patrones de trazo por capa. Réplica de LAYER_QCOLOR, LAYER_WIDTH y _pen
// de app/preview.py, compartida por el visor y la exportación.

export type Fondo = 'claro' | 'oscuro'
export type CapasOcultas = ReadonlySet<string> | readonly string[]

export const FONDO_VISOR = '#23272e'
export const COLOR_DESCONOCIDO = '#ffffff'
export const FUENTE_TEXTO = "'DejaVu Sans', Arial, sans-serif"

const COLOR_VISOR = new Map<string, string>([
  ['EJE', '#e05555'],
  ['CONCRETO', '#f2f2f2'],
  ['ACERO', '#f7d84a'],
  ['ACOTADO', '#67d17c'],
  ['TEXTOS', '#5ec8e8'],
  ['PERFORACIONES', '#6a9fe0'],
  ['SOLDADURA', '#e8955e'],
  ['HACHURADO', '#8a8f98'],
  ['TABLAS', '#f2f2f2'],
  ['OCULTO', '#8a8f98'],
])

/** Paleta para imprimir: trazos oscuros sobre blanco. */
const COLOR_IMPRESION = new Map<string, string>([
  ['EJE', '#555555'],
  ['CONCRETO', '#000000'],
  ['ACERO', '#000000'],
  ['ACOTADO', '#000000'],
  ['TEXTOS', '#000000'],
  ['PERFORACIONES', '#333333'],
  ['SOLDADURA', '#000000'],
  ['HACHURADO', '#888888'],
  ['TABLAS', '#000000'],
  ['OCULTO', '#888888'],
])

/** Ancho base en píxeles por capa (LAYER_WIDTH). */
const ANCHO_CAPA = new Map<string, number>([
  ['EJE', 1.0],
  ['CONCRETO', 1.6],
  ['ACERO', 2.6],
  ['ACOTADO', 1.1],
  ['TEXTOS', 1.1],
  ['PERFORACIONES', 1.2],
  ['SOLDADURA', 1.2],
  ['HACHURADO', 0.8],
  ['TABLAS', 1.2],
  ['OCULTO', 1.0],
])

export function colorCapa(capa: string, fondo: Fondo = 'oscuro'): string {
  if (fondo === 'claro') return COLOR_IMPRESION.get(capa) ?? '#000000'
  return COLOR_VISOR.get(capa) ?? COLOR_DESCONOCIDO
}

/**
 * Ancho de trazo en píxeles de pantalla: max(1, ancho_capa + ancho_mm * 0.05).
 * Solo líneas y polilíneas aportan su ancho propio (`anchoMm`); el resto pasa 0.
 */
export function anchoTrazoPx(capa: string, anchoMm = 0): number {
  return Math.max(1, (ANCHO_CAPA.get(capa) ?? 1.0) + anchoMm * 0.05)
}

/** Patrón de trazo en múltiplos del ancho (como Qt::DashLine y Qt::DotLine). */
export function patronTrazo(capa: string): readonly [number, number] | null {
  if (capa === 'EJE') return [4, 2]
  if (capa === 'OCULTO') return [1, 3]
  return null
}

/** Valor de stroke-dasharray para un ancho dado, o undefined si la capa es continua. */
export function dashArray(capa: string, ancho: number): string | undefined {
  const p = patronTrazo(capa)
  return p ? p.map(k => k * ancho).join(' ') : undefined
}

/** Normaliza las capas ocultas (estado en array o Set) a un Set. */
export function toSet(capas: CapasOcultas): ReadonlySet<string> {
  const conHas = capas as ReadonlySet<string>
  return typeof conHas.has === 'function' ? conHas : new Set(capas as readonly string[])
}
