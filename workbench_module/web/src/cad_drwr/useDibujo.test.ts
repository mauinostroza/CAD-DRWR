import { act, renderHook, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { pedirDibujo, type DibujoRespuesta } from './api'
import { CACHE_MAX, useDibujo } from './useDibujo'
import type { Lamina, Params } from './tipos'

afterEach(cleanup)

vi.mock('./api', () => ({ pedirDibujo: vi.fn() }))

const pedir = vi.mocked(pedirDibujo)
const LAMINA: Lamina = { activa: false, proyecto: '', numero_plano: '', revision: '' }

function dibujo(hash: string): DibujoRespuesta {
  return {
    th: 1,
    bounds: [0, 0, 10, 10],
    render: [],
    cad: [],
    n_render: 0,
    n_cad: 0,
    modulo: 'placa_base',
    hash,
    solapes: [],
  }
}

/** Avanza el reloj falso y deja correr las promesas pendientes. */
async function avanzar(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  pedir.mockReset()
  pedir.mockImplementation(async (_m, p) => dibujo(String(p.B)))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useDibujo', () => {
  it('aplica un debounce de 150 ms y envía los parámetros finales', async () => {
    const { result, rerender } = renderHook(({ p }: { p: Params }) => useDibujo('placa_base', p, LAMINA), {
      initialProps: { p: { B: 440 } },
    })
    expect(result.current.cargando).toBe(true)

    rerender({ p: { B: 450 } })
    await avanzar(100)
    rerender({ p: { B: 460 } })
    await avanzar(149)
    expect(pedir).not.toHaveBeenCalled()

    await avanzar(1)
    expect(pedir).toHaveBeenCalledTimes(1)
    expect(pedir).toHaveBeenCalledWith('placa_base', { B: 460 }, LAMINA, expect.any(AbortSignal))
    expect(result.current.dibujo?.hash).toBe('460')
    expect(result.current.cargando).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('cancela la petición anterior cuando cambian los parámetros', async () => {
    const señales: AbortSignal[] = []
    pedir.mockImplementation((_m, _p, _l, signal) => {
      señales.push(signal as AbortSignal)
      return new Promise<DibujoRespuesta>(() => {})
    })
    const { rerender } = renderHook(({ p }: { p: Params }) => useDibujo('placa_base', p, LAMINA), {
      initialProps: { p: { B: 440 } },
    })
    await avanzar(150)
    rerender({ p: { B: 500 } })
    await avanzar(150)

    expect(señales).toHaveLength(2)
    expect(señales[0].aborted).toBe(true)
    expect(señales[1].aborted).toBe(false)
  })

  it('reutiliza la caché al volver a unos parámetros ya calculados', async () => {
    const { result, rerender } = renderHook(({ p }: { p: Params }) => useDibujo('placa_base', p, LAMINA), {
      initialProps: { p: { B: 440 } },
    })
    await avanzar(150)
    rerender({ p: { B: 500 } })
    await avanzar(150)
    expect(pedir).toHaveBeenCalledTimes(2)

    rerender({ p: { B: 440 } })
    expect(pedir).toHaveBeenCalledTimes(2)
    expect(result.current.dibujo?.hash).toBe('440')
    expect(result.current.cargando).toBe(false)
  })

  it('limita la caché a 32 entradas y expulsa la más antigua', async () => {
    const { rerender } = renderHook(({ p }: { p: Params }) => useDibujo('placa_base', p, LAMINA), {
      initialProps: { p: { B: 1 } },
    })
    await avanzar(150)
    for (let i = 2; i <= CACHE_MAX + 1; i++) {
      rerender({ p: { B: i } })
      await avanzar(150)
    }
    expect(pedir).toHaveBeenCalledTimes(CACHE_MAX + 1)

    // El 1 fue expulsado: hay que pedirlo otra vez.
    rerender({ p: { B: 1 } })
    await avanzar(150)
    expect(pedir).toHaveBeenCalledTimes(CACHE_MAX + 2)

    // El más reciente sigue en caché.
    rerender({ p: { B: CACHE_MAX + 1 } })
    expect(pedir).toHaveBeenCalledTimes(CACHE_MAX + 2)
  })

  it('mantiene el último dibujo mientras carga y muestra el error aparte', async () => {
    let rechazar!: (e: Error) => void
    pedir.mockResolvedValueOnce(dibujo('a'))
    pedir.mockImplementationOnce(
      () =>
        new Promise<DibujoRespuesta>((_, rej) => {
          rechazar = rej
        }),
    )
    const { result, rerender } = renderHook(({ p }: { p: Params }) => useDibujo('placa_base', p, LAMINA), {
      initialProps: { p: { B: 440 } },
    })
    await avanzar(150)
    expect(result.current.dibujo?.hash).toBe('a')

    rerender({ p: { B: 500 } })
    await avanzar(150)
    expect(result.current.cargando).toBe(true)
    expect(result.current.dibujo?.hash).toBe('a')

    await act(async () => {
      rechazar(new Error('Dimensión inválida'))
    })
    expect(result.current.error).toBe('Dimensión inválida')
    expect(result.current.dibujo?.hash).toBe('a')
    expect(result.current.cargando).toBe(false)
  })

  it('no llama al servidor en un módulo interactivo sin geometría', async () => {
    const { result } = renderHook(() => useDibujo('fundacion_sap', { escala: '1:50' }, LAMINA))
    await avanzar(500)

    expect(pedir).not.toHaveBeenCalled()
    expect(result.current).toMatchObject({ dibujo: null, error: null, cargando: false })
  })

  it('trata `_geom: null` (valor por defecto del servidor) como ausencia de geometría', async () => {
    const params = { escala: '1:50', _geom: null } as unknown as Params
    const { result } = renderHook(() => useDibujo('fundacion_sap', params, LAMINA))
    await avanzar(500)

    expect(pedir).not.toHaveBeenCalled()
    expect(result.current).toMatchObject({ dibujo: null, error: null, cargando: false })
  })

  it('sí pide el dibujo en un módulo interactivo cuando hay geometría', async () => {
    renderHook(() => useDibujo('fundacion_sap', { escala: '1:50', _geom: 'geometria' }, LAMINA))
    await avanzar(150)

    expect(pedir).toHaveBeenCalledTimes(1)
    expect(pedir.mock.calls[0][0]).toBe('fundacion_sap')
  })
})
