// Estado del módulo en project.state['cad_drwr'] (JSON, <5 MB, sin resultados de cálculo).
import type { Lamina, Params } from './tipos'

export const SCHEMA_VERSION = 1
export const MAX_PLANTILLAS = 50
export const MAX_GEOM_BYTES = 500_000

export type Plantilla = { id: string; nombre: string; modulo: string; params: Params }

export type EstadoCadDrwr = {
  schema_version: 1
  modulo: string
  /** Últimos parámetros editados por módulo (solo los valores del usuario). */
  params: Record<string, Params>
  lamina: Lamina
  plantillas: Plantilla[]
  /** Geometría SAP2000 leída (FundacionGeom.to_dict) si cabe en el estado. */
  geom?: unknown
  capasOcultas: string[]
  [extra: string]: unknown
}

const LAMINA_INICIAL: Lamina = { activa: false, proyecto: '', numero_plano: '', revision: '' }

export const ESTADO_INICIAL: EstadoCadDrwr = Object.freeze({
  schema_version: 1,
  modulo: 'placa_base',
  params: {},
  lamina: { ...LAMINA_INICIAL },
  plantillas: [],
  capasOcultas: [],
}) as EstadoCadDrwr

const esObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v)

function paramsSeguros(v: unknown): Params {
  const out: Params = {}
  if (!esObj(v)) return out
  for (const [k, x] of Object.entries(v)) {
    if (typeof x === 'string' || typeof x === 'boolean') out[k] = x
    else if (typeof x === 'number' && Number.isFinite(x)) out[k] = x
  }
  return out
}

/** Nunca lanza: normaliza cualquier valor guardado (incluye versiones futuras y plantillas legacy). */
export function migrarEstado(raw: unknown): EstadoCadDrwr {
  if (!esObj(raw)) return { ...ESTADO_INICIAL, params: {}, plantillas: [], capasOcultas: [] }
  const { schema_version: _v, modulo, params, lamina, plantillas, geom, capasOcultas, ...extras } = raw
  const l = esObj(lamina) ? lamina : {}
  const salida: EstadoCadDrwr = {
    ...extras,
    schema_version: 1,
    modulo: typeof modulo === 'string' && modulo ? modulo : 'placa_base',
    params: {},
    lamina: {
      activa: l.activa === true,
      proyecto: typeof l.proyecto === 'string' ? l.proyecto : '',
      numero_plano: typeof l.numero_plano === 'string' ? l.numero_plano : '',
      revision: typeof l.revision === 'string' ? l.revision : '',
    },
    plantillas: [],
    capasOcultas: Array.isArray(capasOcultas)
      ? capasOcultas.filter((c): c is string => typeof c === 'string')
      : [],
  }
  if (esObj(params)) {
    for (const [mod, p] of Object.entries(params)) salida.params[mod] = paramsSeguros(p)
  }
  if (Array.isArray(plantillas)) {
    for (const t of plantillas.slice(0, MAX_PLANTILLAS)) {
      if (
        esObj(t) &&
        typeof t.id === 'string' &&
        typeof t.nombre === 'string' &&
        typeof t.modulo === 'string'
      ) {
        salida.plantillas.push({
          id: t.id,
          nombre: t.nombre,
          modulo: t.modulo,
          params: paramsSeguros(t.params),
        })
      }
    }
  }
  if (geom !== undefined && geom !== null && JSON.stringify(geom).length <= MAX_GEOM_BYTES) {
    salida.geom = geom
  }
  return salida
}

export function aJsonSeguro(e: EstadoCadDrwr): unknown {
  return JSON.parse(JSON.stringify(migrarEstado(e)))
}

/**
 * Plantilla JSON del escritorio (sin versión ni id de módulo): devuelve los parámetros
 * (sin claves derivadas `_escala`) y, si trae `_geom`, la geometría.
 */
export function importarPlantillaEscritorio(
  raw: unknown,
): { params: Params; geom?: unknown; lamina?: Partial<Lamina> } | null {
  if (!esObj(raw)) return null
  const { _escala: _e, _geom, _sheet_metadata, _sheet_enabled, ...resto } = raw
  const params = paramsSeguros(resto)
  if (Object.keys(params).length === 0 && !_geom) return null
  const meta = esObj(_sheet_metadata) ? _sheet_metadata : {}
  return {
    params,
    geom: esObj(_geom) ? _geom : undefined,
    lamina: {
      activa: _sheet_enabled === true,
      proyecto: typeof meta.proyecto === 'string' ? meta.proyecto : '',
      numero_plano: typeof meta.numero_plano === 'string' ? meta.numero_plano : '',
      revision: typeof meta.revision === 'string' ? meta.revision : '',
    },
  }
}
