import { describe, expect, it } from 'vitest'
import { aJsonSeguro, importarPlantillaEscritorio, MAX_GEOM_BYTES, migrarEstado } from './estado'

describe('migrarEstado', () => {
  it('no lanza con basura y devuelve el estado inicial', () => {
    for (const x of [null, undefined, 3, 'x', [], {}]) {
      const e = migrarEstado(x)
      expect(e.schema_version).toBe(1)
      expect(e.modulo).toBe('placa_base')
      expect(e.params).toEqual({})
    }
  })
  it('conserva claves desconocidas y filtra valores no válidos', () => {
    const e = migrarEstado({
      schema_version: 9,
      modulo: 'perfil',
      futuro: { a: 1 },
      params: { perfil: { d: 10, x: Number.NaN, s: 'a', o: { z: 1 } }, malo: 5 },
      plantillas: [{ id: '1', nombre: 'n', modulo: 'perfil', params: { d: 1 } }, { id: 2 }],
    })
    expect(e.futuro).toEqual({ a: 1 })
    expect(e.params.perfil).toEqual({ d: 10, s: 'a' })
    expect(e.params.malo).toEqual({})
    expect(e.plantillas).toHaveLength(1)
  })
  it('descarta geometría demasiado grande', () => {
    const grande = { x: 'a'.repeat(MAX_GEOM_BYTES + 10) }
    expect(migrarEstado({ geom: grande }).geom).toBeUndefined()
    expect(migrarEstado({ geom: { zapatas: [] } }).geom).toEqual({ zapatas: [] })
  })
  it('aJsonSeguro es idempotente', () => {
    const a = aJsonSeguro(migrarEstado({ modulo: 'losa', params: { losa: { L: 400 } } }))
    expect(aJsonSeguro(migrarEstado(a))).toEqual(a)
  })
})

describe('importarPlantillaEscritorio', () => {
  it('quita _escala y rescata la geometría y la lámina', () => {
    const r = importarPlantillaEscritorio({
      perfil: 'W250X25',
      t: 12,
      _escala: 5,
      _geom: { zapatas: [] },
      _sheet_enabled: true,
      _sheet_metadata: { proyecto: 'P', revision: 'A' },
    })
    expect(r?.params).toEqual({ perfil: 'W250X25', t: 12 })
    expect(r?.geom).toEqual({ zapatas: [] })
    expect(r?.lamina).toMatchObject({ activa: true, proyecto: 'P', revision: 'A' })
  })
  it('rechaza lo que no es plantilla', () => {
    expect(importarPlantillaEscritorio(null)).toBeNull()
    expect(importarPlantillaEscritorio({})).toBeNull()
  })
})
