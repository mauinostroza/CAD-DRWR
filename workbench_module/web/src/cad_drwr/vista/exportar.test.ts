import { describe, expect, it } from 'vitest'
import type { DibujoJson } from '../tipos'
import { aPngBlob, aSvg } from './exportar'

const dibujo: DibujoJson = {
  th: 12,
  bounds: [0, 0, 100, 50],
  n_render: 6,
  n_cad: 6,
  cad: [],
  render: [
    { t: 'line', a: [0, 0], b: [100, 0], l: 'CONCRETO', w: 0 },
    { t: 'line', a: [1.5, 2.5], b: [7.5, 8.5], l: 'ACERO', w: 0 },
    { t: 'circle', c: [20, 20], r: 5, l: 'EJE', f: false },
    { t: 'arc', c: [60, 20], r: 10, a1: 0, a2: 270, ccw: true, l: 'CONCRETO' },
    {
      t: 'poly',
      p: [
        [0, 40],
        [10, 40],
        [10, 50],
      ],
      z: true,
      l: 'OCULTO',
      w: 0,
    },
    {
      t: 'filled',
      p: [
        [80, 5],
        [90, 5],
        [85, 15],
      ],
      l: 'HACHURADO',
    },
    { t: 'text', p: [50, 45], s: 'A & B <x> "q"', h: 4, rot: 30, l: 'TEXTOS', ha: 'c', va: 'm' },
  ],
}

const parsear = (svg: string): Document => new DOMParser().parseFromString(svg, 'image/svg+xml')

describe('aSvg', () => {
  it('produce XML válido, sin parsererror', () => {
    const doc = parsear(aSvg(dibujo))
    expect(doc.getElementsByTagName('parsererror').length).toBe(0)
    expect(doc.documentElement.localName).toBe('svg')
    expect(doc.documentElement.getAttribute('xmlns')).toBe('http://www.w3.org/2000/svg')
  })

  it('viewBox = bounds más margen, con Y invertida en el viewBox', () => {
    const svg = aSvg(dibujo, { margenMm: 10 })
    // x0-10, -(y1+10), ancho 100+20, alto 50+20
    expect(svg).toContain('viewBox="-10 -60 120 70"')
    expect(svg).toContain('width="120mm"')
    expect(svg).toContain('height="70mm"')
  })

  it('sin bounds usa un marco de 100 mm centrado en el origen', () => {
    const svg = aSvg({ ...dibujo, bounds: null }, { margenMm: 0 })
    expect(svg).toContain('viewBox="-50 -50 100 100"')
  })

  it('omite las capas ocultas', () => {
    const svg = aSvg(dibujo, { capasOcultas: ['ACERO'] })
    expect(svg).not.toContain('x1="1.5"')
    expect(svg).toContain('x1="0"')
  })

  it('acepta capas ocultas como Set', () => {
    const svg = aSvg(dibujo, { capasOcultas: new Set(['ACERO']) })
    expect(svg).not.toContain('x1="1.5"')
  })

  it('no contiene scripts, enlaces ni recursos externos', () => {
    const svg = aSvg(dibujo)
    expect(svg).not.toMatch(/<script/i)
    expect(svg).not.toMatch(/href|src=|url\(/i)
    // La única URL permitida es el espacio de nombres SVG.
    expect(svg.replace('http://www.w3.org/2000/svg', '')).not.toMatch(/http/i)
  })

  it('escapa el texto', () => {
    const svg = aSvg(dibujo)
    expect(svg).toContain('A &amp; B &lt;x&gt; &quot;q&quot;')
    expect(parsear(svg).getElementsByTagName('parsererror').length).toBe(0)
  })

  it('el texto se contra-voltea y lleva la rotación negada', () => {
    const svg = aSvg(dibujo)
    expect(svg).toContain('transform="translate(50 45) scale(1 -1) rotate(-30)"')
    expect(svg).toContain('text-anchor="middle"')
    expect(svg).toContain('dominant-baseline="central"')
    expect(svg).toContain('font-size="4"')
  })

  it('paleta clara sobre blanco; oscura con el fondo del visor', () => {
    expect(aSvg(dibujo)).toContain('fill="#ffffff"')
    expect(aSvg(dibujo)).not.toContain('#23272e')
    expect(aSvg(dibujo, { fondo: 'oscuro' })).toContain('fill="#23272e"')
    expect(aSvg(dibujo, { fondo: 'oscuro' })).toContain('stroke="#f2f2f2"')
  })

  it('el trazo EJE es discontinuo y el OCULTO punteado', () => {
    const svg = aSvg(dibujo)
    const eje = svg.match(/<circle[^>]*stroke-dasharray[^>]*\/>/)
    expect(eje).not.toBeNull()
    expect(svg).toMatch(/<path d="M 0 40 L 10 40 L 10 50 Z"[^>]*stroke-dasharray/)
  })

  it('el arco usa el mismo path que la vista (barrido de 270 con large-arc)', () => {
    const svg = aSvg(dibujo)
    expect(svg).toMatch(/<path d="M 70 20 A 10 10 0 1 1 60 10"/)
  })
})

describe('aPngBlob', () => {
  it('se exporta como función (la rasterización necesita navegador real)', () => {
    expect(typeof aPngBlob).toBe('function')
  })
})
