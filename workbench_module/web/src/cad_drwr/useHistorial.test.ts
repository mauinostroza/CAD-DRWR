import { act, renderHook, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useHistorial } from './useHistorial'

afterEach(cleanup)

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useHistorial', () => {
  it('deshace y rehace cambios sin origen', () => {
    const { result } = renderHook(() => useHistorial(0))
    act(() => result.current.fijar(1))
    act(() => result.current.fijar(2))

    expect(result.current.valor).toBe(2)
    act(() => result.current.deshacer())
    expect(result.current.valor).toBe(1)
    act(() => result.current.deshacer())
    expect(result.current.valor).toBe(0)
    expect(result.current.puedeDeshacer).toBe(false)

    act(() => result.current.rehacer())
    expect(result.current.valor).toBe(1)
    expect(result.current.puedeRehacer).toBe(true)
  })

  it('no crea un paso si el valor no cambia', () => {
    const { result } = renderHook(() => useHistorial('a'))
    act(() => result.current.fijar('a'))
    expect(result.current.puedeDeshacer).toBe(false)
  })

  it('agrupa cambios seguidos del mismo origen en menos de 500 ms', () => {
    const { result } = renderHook(() => useHistorial(0))
    act(() => result.current.fijar(1, 'B'))
    vi.advanceTimersByTime(200)
    act(() => result.current.fijar(2, 'B'))
    vi.advanceTimersByTime(200)
    act(() => result.current.fijar(3, 'B'))

    expect(result.current.valor).toBe(3)
    act(() => result.current.deshacer())
    expect(result.current.valor).toBe(0)
    expect(result.current.puedeDeshacer).toBe(false)
  })

  it('no agrupa si pasan 500 ms o si cambia el origen', () => {
    const { result } = renderHook(() => useHistorial(0))
    act(() => result.current.fijar(1, 'B'))
    vi.advanceTimersByTime(500)
    act(() => result.current.fijar(2, 'B'))
    vi.advanceTimersByTime(100)
    act(() => result.current.fijar(3, 'C'))

    act(() => result.current.deshacer())
    expect(result.current.valor).toBe(2)
    act(() => result.current.deshacer())
    expect(result.current.valor).toBe(1)
    act(() => result.current.deshacer())
    expect(result.current.valor).toBe(0)
  })

  it('un cambio nuevo borra el futuro', () => {
    const { result } = renderHook(() => useHistorial(0))
    act(() => result.current.fijar(1))
    act(() => result.current.fijar(2))
    act(() => result.current.deshacer())
    expect(result.current.puedeRehacer).toBe(true)

    act(() => result.current.fijar(3))
    expect(result.current.puedeRehacer).toBe(false)
  })

  it('respeta el máximo de pasos', () => {
    const { result } = renderHook(() => useHistorial(0, 3))
    for (let i = 1; i <= 5; i++) act(() => result.current.fijar(i))

    expect(result.current.valor).toBe(5)
    for (let i = 0; i < 3; i++) act(() => result.current.deshacer())
    expect(result.current.valor).toBe(2)
    expect(result.current.puedeDeshacer).toBe(false)
  })

  it('tras deshacer, un cambio con el mismo origen inmediato es un paso nuevo', () => {
    const { result } = renderHook(() => useHistorial(0))
    act(() => result.current.fijar(1, 'B'))
    act(() => result.current.deshacer())
    act(() => result.current.fijar(2, 'B'))

    act(() => result.current.deshacer())
    expect(result.current.valor).toBe(0)
    expect(result.current.puedeDeshacer).toBe(false)
  })
})
