import { describe, expect, it } from 'vitest'
import type { EntArco, EntRender } from '../tipos'
import {
  ajustarVista,
  aModelo,
  aPantalla,
  anclajeTexto,
  barridoArco,
  medir,
  pathArco,
  pathPoligono,
  snaps,
  transformacion,
  transformTexto,
  zoomHaciaCursor,
  type Vista,
} from './geometria'

const arco = (a1: number, a2: number, ccw: boolean, c: [number, number] = [0, 0], r = 10): EntArco => ({
  t: 'arc',
  c,
  r,
  a1,
  a2,
  ccw,
  l: 'CONCRETO',
})

/**
 * Punto medio del arco de un path "M x0 y0 A r r 0 large sweep x1 y1", calculado con el
 * algoritmo de conversión de parámetros de SVG (F.6.5), independiente de pathArco.
 */
function puntoMedioSvg(d: string): [number, number] {
  const t = d.trim().split(/\s+/)
  const x1 = Number(t[1])
  const y1 = Number(t[2])
  const r = Number(t[4])
  const fA = Number(t[7])
  const fS = Number(t[8])
  const x2 = Number(t[9])
  const y2 = Number(t[10])
  const dx = (x1 - x2) / 2
  const dy = (y1 - y2) / 2
  const d2 = dx * dx + dy * dy
  const s = Math.sqrt(Math.max(0, (r * r - d2) / d2))
  const signo = fA !== fS ? 1 : -1
  const cxp = signo * s * dy
  const cyp = -signo * s * dx
  const cx = cxp + (x1 + x2) / 2
  const cy = cyp + (y1 + y2) / 2
  const th1 = Math.atan2((dy - cyp) / r, (dx - cxp) / r)
  const th2 = Math.atan2((-dy - cyp) / r, (-dx - cxp) / r)
  let dth = th2 - th1
  if (fS === 0 && dth > 0) dth -= 2 * Math.PI
  if (fS === 1 && dth < 0) dth += 2 * Math.PI
  const tm = th1 + dth / 2
  return [cx + r * Math.cos(tm), cy + r * Math.sin(tm)]
}

describe('ajustarVista', () => {
  it('encaja la caja con margen y centra en su punto medio', () => {
    const v = ajustarVista([0, 0, 1000, 500], 500, 400)
    expect(v.escala).toBeCloseTo(0.41, 9) // min(410/1000, 310/500)
    expect(v.cx).toBe(500)
    expect(v.cy).toBe(250)
  })

  it('sin caja usa escala 0.2 centrada en 0,0', () => {
    expect(ajustarVista(null, 800, 600)).toEqual({ escala: 0.2, cx: 0, cy: 0 })
  })

  it('no baja de la escala mínima 1e-4', () => {
    expect(ajustarVista([0, 0, 1000, 1000], 50, 50).escala).toBe(1e-4)
  })
})

describe('zoomHaciaCursor', () => {
  const v: Vista = { escala: 0.5, cx: 100, cy: -40 }

  it('conserva bajo el cursor el punto de modelo', () => {
    const px = 130
    const py = 210
    const antes = aModelo(v, px, py, 640, 480)
    const z = zoomHaciaCursor(v, 3, px, py, 640, 480)
    const despues = aPantalla(z, antes[0], antes[1], 640, 480)
    expect(despues[0]).toBeCloseTo(px, 9)
    expect(despues[1]).toBeCloseTo(py, 9)
  })

  it('aplica el factor 1.15^delta', () => {
    const z = zoomHaciaCursor(v, 2, 320, 240, 640, 480)
    expect(z.escala / v.escala).toBeCloseTo(1.15 ** 2, 12)
  })

  it('delta 0 devuelve la misma vista', () => {
    expect(zoomHaciaCursor(v, 0, 10, 10, 640, 480)).toBe(v)
  })

  it('limita el cambio relativo a 1e4 por paso', () => {
    const z = zoomHaciaCursor(v, 1000, 0, 0, 640, 480)
    expect(z.escala).toBeCloseTo(v.escala * 1e4, 6)
  })
})

describe('aPantalla / aModelo', () => {
  const v: Vista = { escala: 2, cx: 10, cy: 20 }

  it('el centro del modelo cae en el centro de la pantalla', () => {
    expect(aPantalla(v, 10, 20, 400, 300)).toEqual([200, 150])
  })

  it('invierte Y: lo que está más arriba en el modelo queda más arriba en pantalla', () => {
    const arriba = aPantalla(v, 10, 30, 400, 300)
    expect(arriba[1]).toBe(150 - 20)
  })

  it('aModelo es la inversa de aPantalla', () => {
    const p = aPantalla(v, -3.5, 7.25, 400, 300)
    const m = aModelo(v, p[0], p[1], 400, 300)
    expect(m[0]).toBeCloseTo(-3.5, 9)
    expect(m[1]).toBeCloseTo(7.25, 9)
  })
})

describe('barridoArco', () => {
  it.each([
    [0, 90, true, 90],
    [270, 90, true, 180],
    [30, 30, true, 360],
    [90, 0, false, -90],
    [0, 0, false, -360],
  ])('a1=%d a2=%d ccw=%s -> %d', (a1, a2, ccw, esperado) => {
    expect(barridoArco(arco(a1, a2, ccw))).toBe(esperado)
  })
})

describe('pathArco', () => {
  const casos: Array<[number, number, boolean]> = [
    [0, 90, true],
    [0, 180, true],
    [0, 270, true],
    [20, 200, true],
    [90, 0, false],
    [270, 90, false],
    [0, 270, false],
  ]

  it.each(casos)('arco a1=%d a2=%d ccw=%s: extremos y punto medio correctos', (a1, a2, ccw) => {
    const a = arco(a1, a2, ccw, [5, -7], 10)
    const s = barridoArco(a)
    const d = pathArco(a)
    const t = d.trim().split(/\s+/)
    const rad = (g: number) => (g * Math.PI) / 180
    expect(Number(t[1])).toBeCloseTo(5 + 10 * Math.cos(rad(a1)), 5)
    expect(Number(t[2])).toBeCloseTo(-7 + 10 * Math.sin(rad(a1)), 5)
    expect(Number(t[9])).toBeCloseTo(5 + 10 * Math.cos(rad(a1 + s)), 5)
    expect(Number(t[10])).toBeCloseTo(-7 + 10 * Math.sin(rad(a1 + s)), 5)

    // Con barrido de 180 el centro está mal condicionado: el redondeo del path desplaza el
    // punto medio unas milésimas, así que se tolera 2 decimales en ese caso.
    const precision = Math.abs(s) === 180 ? 2 : 5
    const [mx, my] = puntoMedioSvg(d)
    expect(mx).toBeCloseTo(5 + 10 * Math.cos(rad(a1 + s / 2)), precision)
    expect(my).toBeCloseTo(-7 + 10 * Math.sin(rad(a1 + s / 2)), precision)
  })

  it('flag large-arc solo para barridos mayores de 180', () => {
    expect(pathArco(arco(0, 90, true)).split(' ')[7]).toBe('0')
    expect(pathArco(arco(0, 270, true)).split(' ')[7]).toBe('1')
  })

  it('flag de sentido: 1 en antihorario de modelo, 0 en horario', () => {
    expect(pathArco(arco(0, 90, true)).split(' ')[8]).toBe('1')
    expect(pathArco(arco(90, 0, false)).split(' ')[8]).toBe('0')
  })

  it('360 grados se parte en dos semiarcos', () => {
    const d = pathArco(arco(0, 360, true))
    expect(d.match(/ A /g)?.length).toBe(2)
    // El primer semiarco va de 0 a 180 grados: su punto medio es (0, 10).
    const [mx, my] = puntoMedioSvg(d)
    expect(mx).toBeCloseTo(0, 4)
    expect(my).toBeCloseTo(10, 4)
  })
})

describe('pathPoligono y transformaciones', () => {
  it('pathPoligono abre o cierra el polígono', () => {
    expect(
      pathPoligono(
        [
          [0, 0],
          [1, 2],
        ],
        false,
      ),
    ).toBe('M 0 0 L 1 2')
    expect(
      pathPoligono(
        [
          [0, 0],
          [1, 2],
        ],
        true,
      ),
    ).toBe('M 0 0 L 1 2 Z')
    expect(pathPoligono([], true)).toBe('')
  })

  it('transformacion invierte Y y centra la vista', () => {
    const t = transformacion({ escala: 0.5, cx: 100, cy: 50 }, 400, 300)
    // tx = W/2 - cx*s = 200 - 50; ty = H/2 + cy*s = 150 + 25
    expect(t).toBe('matrix(0.5 0 0 -0.5 150 175)')
  })

  it('transformTexto contra-voltea y aplica la rotación negada', () => {
    expect(transformTexto([3, 4], 0)).toBe('translate(3 4) scale(1 -1)')
    expect(transformTexto([3, 4], 30)).toBe('translate(3 4) scale(1 -1) rotate(-30)')
  })
})

describe('anclajeTexto', () => {
  it.each([
    ['l', 'b', 'start', 'text-after-edge'],
    ['c', 'm', 'middle', 'central'],
    ['r', 't', 'end', 'text-before-edge'],
  ] as const)('ha=%s va=%s', (ha, va, textAnchor, dominantBaseline) => {
    expect(anclajeTexto(ha, va)).toEqual({ textAnchor, dominantBaseline })
  })
})

describe('snaps', () => {
  const render: EntRender[] = [
    { t: 'line', a: [0, 0], b: [100, 0], l: 'CONCRETO', w: 0 },
    { t: 'circle', c: [50, 50], r: 5, l: 'ACERO', f: false },
    {
      t: 'poly',
      p: [
        [0, 100],
        [0, 200],
      ],
      z: false,
      l: 'OCULTO',
      w: 0,
    },
  ]

  it('encuentra extremos, punto medio, centro y vértices', () => {
    expect(snaps(render, 10, 1, [100.5, 0.5])).toEqual([100, 0])
    expect(snaps(render, 10, 1, [49, 51])).toEqual([50, 50])
    expect(snaps(render, 10, 1, [50.5, 0.2])).toEqual([50, 0])
    expect(snaps(render, 10, 1, [0.5, 199])).toEqual([0, 200])
  })

  it('devuelve null fuera de la tolerancia en píxeles', () => {
    expect(snaps(render, 10, 1, [30, 30])).toBeNull()
  })

  it('la tolerancia se mide en píxeles: a más escala, menos distancia en mm', () => {
    // A escala 10 px/mm, 10 px son 1 mm: el punto (101.5, 0) queda fuera.
    expect(snaps(render, 10, 10, [101.5, 0])).toBeNull()
    expect(snaps(render, 10, 1, [101.5, 0])).toEqual([100, 0])
  })
})

describe('medir', () => {
  it('calcula dx, dy, distancia y ángulo en [0, 360)', () => {
    expect(medir([0, 0], [3, 4])).toEqual({
      dx: 3,
      dy: 4,
      dist: 5,
      anguloDeg: (Math.atan2(4, 3) * 180) / Math.PI,
    })
    expect(medir([0, 0], [0, -1]).anguloDeg).toBeCloseTo(270, 9)
    expect(medir([0, 0], [-1, 0]).anguloDeg).toBeCloseTo(180, 9)
  })
})
