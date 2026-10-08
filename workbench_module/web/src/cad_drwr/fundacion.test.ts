import { describe, expect, it } from 'vitest'
import {
  esGeomValida,
  incluirZapata,
  quitarPedestal,
  resumenGeom,
  setEspesorZapata,
  setPedestal,
  type FundacionGeom,
  type ZapataGeom,
} from './fundacion'

function pedestal(frame: string, largo = 400, ancho = 300, largoEnX = true) {
  return {
    frame,
    largo,
    ancho,
    largo_en_x: largoEnX,
    centro: [0, 0] as [number, number],
    punto_pie: 'P1',
    aproximado: false,
    motivo_aviso: '',
  }
}

function zapata(nombre: string, nAreas: number, nPedestales: number): ZapataGeom {
  return {
    nombre,
    areas: Array.from({ length: nAreas }, (_, k) => ({
      nombre: `${nombre}-A${k}`,
      seccion: 'S1',
      espesor: 200,
      pts_nombres: ['1', '2', '3'],
      pts: [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
      ],
      pts_malla: [],
    })),
    contorno: [
      [0, 0],
      [2000, 0],
      [2000, 1500],
      [0, 1500],
    ],
    pedestales: Array.from({ length: nPedestales }, (_, k) => pedestal(`F${nombre}${k}`)),
  }
}

function geom(): FundacionGeom {
  return {
    nombre: 'G1',
    zapatas: [zapata('Z1', 2, 2), zapata('Z2', 1, 0), zapata('Z3', 3, 1)],
  }
}

describe('resumenGeom', () => {
  it('cuenta zapatas, pedestales y áreas', () => {
    expect(resumenGeom(geom())).toEqual({ zapatas: 3, pedestales: 3, areas: 6 })
  })

  it('geometría vacía', () => {
    expect(resumenGeom({ nombre: 'vacia', zapatas: [] })).toEqual({
      zapatas: 0,
      pedestales: 0,
      areas: 0,
    })
  })
})

describe('setEspesorZapata', () => {
  it('fija el espesor en todas las áreas de la zapata indicada', () => {
    const g = setEspesorZapata(geom(), 0, 350)
    expect(g.zapatas[0].areas.map(a => a.espesor)).toEqual([350, 350])
    expect(g.zapatas[1].areas.map(a => a.espesor)).toEqual([200])
    expect(g.zapatas[2].areas.map(a => a.espesor)).toEqual([200, 200, 200])
  })

  it('no modifica la geometría original ni el contorno', () => {
    const original = geom()
    const copia = structuredClone(original)
    const g = setEspesorZapata(original, 2, 400)
    expect(original).toEqual(copia)
    expect(g).not.toBe(original)
    expect(g.zapatas[2].contorno).toEqual(original.zapatas[2].contorno)
    expect(original.zapatas[2].contorno).toHaveLength(4)
  })

  it('valor no válido o índice inexistente no cambia nada', () => {
    const original = geom()
    expect(setEspesorZapata(original, 0, 0)).toEqual(original)
    expect(setEspesorZapata(original, 0, Number.NaN)).toEqual(original)
    expect(setEspesorZapata(original, 9, 300)).toEqual(original)
  })
})

describe('setPedestal', () => {
  it('cambia sólo los campos indicados', () => {
    const g = setPedestal(geom(), 0, 1, { largo: 500, largo_en_x: false })
    expect(g.zapatas[0].pedestales[1]).toEqual({
      ...geom().zapatas[0].pedestales[1],
      largo: 500,
      largo_en_x: false,
    })
    expect(g.zapatas[0].pedestales[0]).toEqual(geom().zapatas[0].pedestales[0])
  })

  it('ignora largo o ancho no positivos o no finitos', () => {
    const original = geom()
    const g = setPedestal(original, 0, 0, { largo: -1, ancho: Number.POSITIVE_INFINITY })
    expect(g.zapatas[0].pedestales[0]).toEqual(original.zapatas[0].pedestales[0])
  })

  it('no reescribe el contorno', () => {
    const original = geom()
    const g = setPedestal(original, 2, 0, { ancho: 350 })
    expect(g.zapatas[2].contorno).toEqual(original.zapatas[2].contorno)
    expect(g.zapatas[2].pedestales[0].ancho).toBe(350)
    expect(original.zapatas[2].pedestales[0].ancho).toBe(300)
  })
})

describe('quitarPedestal', () => {
  it('quita sólo el pedestal indicado', () => {
    const g = quitarPedestal(geom(), 0, 0)
    expect(g.zapatas[0].pedestales.map(p => p.frame)).toEqual(['FZ11'])
    expect(geom().zapatas[0].pedestales).toHaveLength(2)
  })
})

describe('incluirZapata', () => {
  it('devuelve sólo las zapatas indicadas, en su orden', () => {
    const g = incluirZapata(geom(), [2, 0])
    expect(g.zapatas.map(z => z.nombre)).toEqual(['Z1', 'Z3'])
    expect(g.nombre).toBe('G1')
  })

  it('ignora índices fuera de rango y repetidos', () => {
    const g = incluirZapata(geom(), [1, 1, 7])
    expect(g.zapatas.map(z => z.nombre)).toEqual(['Z2'])
  })

  it('lista vacía devuelve geometría sin zapatas', () => {
    expect(incluirZapata(geom(), []).zapatas).toEqual([])
  })
})

describe('esGeomValida', () => {
  it('acepta la forma de FundacionGeom.to_dict()', () => {
    expect(esGeomValida(geom())).toBe(true)
    expect(esGeomValida({ nombre: 'x', zapatas: [] })).toBe(true)
  })

  it('rechaza valores que no son geometría', () => {
    expect(esGeomValida(null)).toBe(false)
    expect(esGeomValida('x')).toBe(false)
    expect(esGeomValida([])).toBe(false)
    expect(esGeomValida({ zapatas: [] })).toBe(false)
    expect(esGeomValida({ nombre: 'x' })).toBe(false)
    expect(esGeomValida({ nombre: 'x', zapatas: [{ nombre: 'Z' }] })).toBe(false)
    expect(esGeomValida({ nombre: 'x', zapatas: [{ nombre: 'Z', areas: [], contorno: [] }] })).toBe(false)
  })
})
