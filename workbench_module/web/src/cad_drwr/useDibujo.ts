// Dibujo CAD-DRWR: debounce, cancelación de la petición anterior, caché LRU por clave estable y
// último dibujo válido visible mientras se recalcula. El error se muestra aparte.
import { useEffect, useMemo, useRef, useState } from 'react'
import { pedirDibujo, type DibujoRespuesta } from './api'
import type { Lamina, Params } from './tipos'

export const DEBOUNCE_MS = 150
export const CACHE_MAX = 32
/** Módulo con panel propio: sin geometría cargada no hay nada que dibujar. */
export const MODULO_INTERACTIVO = 'fundacion_sap'

export type EstadoDibujo = {
  dibujo: DibujoRespuesta | null
  cargando: boolean
  error: string | null
  /** Duración de la última respuesta del servidor (0 si salió de la caché), o null. */
  tiempoMs: number | null
}

const INICIAL: EstadoDibujo = { dibujo: null, cargando: false, error: null, tiempoMs: null }

function ordenar(valor: unknown): unknown {
  if (Array.isArray(valor)) return valor.map(ordenar)
  if (valor !== null && typeof valor === 'object') {
    const src = valor as Record<string, unknown>
    const out: Record<string, unknown> = {}
    for (const k of Object.keys(src).sort()) out[k] = ordenar(src[k])
    return out
  }
  return valor
}

/** Serialización con claves ordenadas: objetos con el mismo contenido dan la misma clave. */
export function claveEstable(valor: unknown): string {
  return JSON.stringify(ordenar(valor))
}

function guardarEnCache(cache: Map<string, DibujoRespuesta>, clave: string, dibujo: DibujoRespuesta): void {
  cache.delete(clave)
  cache.set(clave, dibujo)
  while (cache.size > CACHE_MAX) {
    const antigua = cache.keys().next().value
    if (antigua === undefined) break
    cache.delete(antigua)
  }
}

function mensajeError(e: unknown): string {
  return e instanceof Error ? e.message : 'Error desconocido al calcular el dibujo'
}

/**
 * Dibujo del módulo para los parámetros dados. `params` y `lamina` deben ser referencias
 * estables (useMemo): la clave se recalcula solo cuando cambia su contenido.
 */
export function useDibujo(
  modulo: string,
  params: Params,
  lamina: Lamina,
  interactivo: boolean = modulo === MODULO_INTERACTIVO,
): EstadoDibujo {
  const clave = useMemo(
    () => claveEstable({ modulo, params, lamina, interactivo }),
    [modulo, params, lamina, interactivo],
  )
  const cache = useRef<Map<string, DibujoRespuesta> | null>(null)
  if (cache.current === null) cache.current = new Map()
  const [estado, setEstado] = useState<EstadoDibujo>(INICIAL)

  useEffect(() => {
    const almacen = cache.current ?? new Map<string, DibujoRespuesta>()
    if (!modulo || (interactivo && (params as Record<string, unknown>)._geom == null)) {
      setEstado(INICIAL)
      return
    }
    const previa = almacen.get(clave)
    if (previa) {
      guardarEnCache(almacen, clave, previa)
      setEstado({ dibujo: previa, cargando: false, error: null, tiempoMs: 0 })
      return
    }
    const control = new AbortController()
    setEstado(s => ({ ...s, cargando: true, error: null }))
    const espera = setTimeout(() => {
      const inicio = performance.now()
      pedirDibujo(modulo, params, lamina, control.signal).then(
        dibujo => {
          if (control.signal.aborted) return
          guardarEnCache(almacen, clave, dibujo)
          setEstado({
            dibujo,
            cargando: false,
            error: null,
            tiempoMs: Math.round(performance.now() - inicio),
          })
        },
        (e: unknown) => {
          if (control.signal.aborted) return
          setEstado(s => ({ ...s, cargando: false, error: mensajeError(e) }))
        },
      )
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(espera)
      control.abort()
    }
    // La clave resume modulo, params, lamina e interactivo: son las únicas entradas de la petición.
  }, [clave])

  return estado
}
