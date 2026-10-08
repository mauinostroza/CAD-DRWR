import { describe, expect, it } from 'vitest'
import golden from '../../../backend/motor_calculo/cad_drwr/golden/reglas_ui.json'
import { aplicarCambio, factorEscala, habilitados } from './reglas'
import type { ParamValor, Params } from './tipos'

type Escenario = {
  modulo: string
  nombre: string
  params_antes: Params
  campo: string
  valor: ParamValor
  params_despues: Params
  habilitados: Record<string, boolean>
}

const casos = golden as unknown as Escenario[]

/** Floats con tolerancia 1e-9; resto de tipos, igualdad exacta. */
function coincide(obtenido: ParamValor | undefined, esperado: ParamValor): boolean {
  if (typeof esperado === 'number') {
    return typeof obtenido === 'number' && Math.abs(obtenido - esperado) <= 1e-9
  }
  return obtenido === esperado
}

const etiquetados: [string, Escenario][] = casos.map(c => [`${c.modulo} · ${c.nombre}`, c])

describe('reglas_ui frente al golden del escritorio', () => {
  it('el golden tiene los 59 escenarios esperados', () => {
    expect(casos).toHaveLength(59)
  })

  it.each(etiquetados)('habilitados · %s', (_nombre, c) => {
    expect(habilitados(c.modulo, c.params_despues)).toEqual(c.habilitados)
  })

  it.each(etiquetados)('aplicarCambio · %s', (_nombre, c) => {
    const nuevo = aplicarCambio(c.modulo, c.params_antes, c.campo, c.valor, c.params_antes)
    const claves = new Set([...Object.keys(nuevo), ...Object.keys(c.params_despues)])
    const difs = [...claves].filter(k => !coincide(nuevo[k], c.params_despues[k]))
    expect(difs).toEqual([])
    expect(nuevo._escala).toBe(c.params_despues._escala)
  })
})

describe('reglas_ui: casos fuera del golden', () => {
  it('factorEscala devuelve n/10 y 5 si no parsea', () => {
    expect(factorEscala('1:50')).toBe(5)
    expect(factorEscala('1:20')).toBe(2)
    expect(factorEscala('1:100')).toBe(10)
    expect(factorEscala('x')).toBe(5)
    expect(factorEscala('1:')).toBe(5)
  })

  it('un módulo sin reglas (fundacion_sap o inexistente) lanza error', () => {
    expect(() => habilitados('fundacion_sap', {})).toThrow()
    expect(() => habilitados('no_existe', {})).toThrow()
  })

  it('losa no tiene reglas: todo queda habilitado', () => {
    const res = habilitados('losa', casos[0].params_despues)
    expect(Object.values(res).every(Boolean)).toBe(true)
  })
})
