// Historial deshacer/rehacer genérico. Cambios seguidos con el mismo origen (<500 ms entre sí)
// forman un solo paso. Sin origen no se agrupa nada.
import { useCallback, useMemo, useState } from 'react'

export const VENTANA_AGRUPADO_MS = 500

type Pila<T> = {
  past: T[]
  present: T
  future: T[]
  origen: string | undefined
  ultimo: number
}

export type Historial<T> = {
  valor: T
  fijar: (v: T, origen?: string) => void
  deshacer: () => void
  rehacer: () => void
  puedeDeshacer: boolean
  puedeRehacer: boolean
}

export function useHistorial<T>(inicial: T, max = 50): Historial<T> {
  const [pila, setPila] = useState<Pila<T>>(() => ({
    past: [],
    present: inicial,
    future: [],
    origen: undefined,
    ultimo: 0,
  }))

  const fijar = useCallback(
    (v: T, origen?: string) => {
      setPila(p => {
        if (Object.is(v, p.present)) return p
        const ahora = Date.now()
        const agrupa = origen !== undefined && origen === p.origen && ahora - p.ultimo < VENTANA_AGRUPADO_MS
        if (agrupa) return { ...p, present: v, future: [], ultimo: ahora }
        const past = [...p.past, p.present]
        if (past.length > max) past.splice(0, past.length - max)
        return { past, present: v, future: [], origen, ultimo: ahora }
      })
    },
    [max],
  )

  const deshacer = useCallback(() => {
    setPila(p => {
      if (p.past.length === 0) return p
      return {
        past: p.past.slice(0, -1),
        present: p.past[p.past.length - 1],
        future: [p.present, ...p.future],
        origen: undefined,
        ultimo: 0,
      }
    })
  }, [])

  const rehacer = useCallback(() => {
    setPila(p => {
      if (p.future.length === 0) return p
      return {
        past: [...p.past, p.present],
        present: p.future[0],
        future: p.future.slice(1),
        origen: undefined,
        ultimo: 0,
      }
    })
  }, [])

  return useMemo(
    () => ({
      valor: pila.present,
      fijar,
      deshacer,
      rehacer,
      puedeDeshacer: pila.past.length > 0,
      puedeRehacer: pila.future.length > 0,
    }),
    [pila, fijar, deshacer, rehacer],
  )
}
