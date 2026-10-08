import { fireEvent, render, screen, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DibujoJson } from '../tipos'
import { aPantalla, aModelo, pathArco, transformacion, type Vista } from './geometria'
import { VistaSvg } from './VistaSvg'

afterEach(cleanup)

// jsdom no siempre trae PointerEvent: se usa un MouseEvent con pointerId como respaldo.
if (typeof window.PointerEvent === 'undefined') {
  class PointerEventPoly extends MouseEvent {
    pointerId: number
    constructor(type: string, init: PointerEventInit = {}) {
      super(type, init)
      this.pointerId = init.pointerId ?? 0
    }
  }
  window.PointerEvent = PointerEventPoly as unknown as typeof PointerEvent
}

const CONTENEDOR = 500
const rectDe = (w: number, h: number) =>
  ({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: w,
    bottom: h,
    width: w,
    height: h,
    toJSON() {},
  }) as DOMRect

/** Con bounds 0..1000 y contenedor 500x500, la vista ajustada es escala 0.41 centrada en 500,500. */
const VISTA_AJUSTADA: Vista = { escala: 0.41, cx: 500, cy: 500 }
const T_AJUSTADA = transformacion(VISTA_AJUSTADA, CONTENEDOR, CONTENEDOR)

const dibujo: DibujoJson = {
  th: 12,
  bounds: [0, 0, 1000, 1000],
  n_render: 7,
  n_cad: 7,
  cad: [],
  render: [
    { t: 'line', a: [100, 200], b: [400, 600], l: 'CONCRETO', w: 0 },
    { t: 'circle', c: [500, 500], r: 50, l: 'ACERO', f: false },
    { t: 'arc', c: [800, 200], r: 100, a1: 0, a2: 90, ccw: true, l: 'CONCRETO' },
    {
      t: 'poly',
      p: [
        [100, 800],
        [200, 800],
        [200, 900],
      ],
      z: false,
      l: 'OCULTO',
      w: 0,
    },
    {
      t: 'filled',
      p: [
        [600, 100],
        [700, 100],
        [650, 200],
      ],
      l: 'ACOTADO',
    },
    { t: 'text', p: [300, 900], s: 'Texto', h: 20, rot: 0, l: 'TEXTOS', ha: 'c', va: 'm' },
    { t: 'line', a: [0, 500], b: [1000, 500], l: 'EJE', w: 0 },
  ],
}

const svg = () => screen.getByRole('img') as unknown as SVGSVGElement
const raiz = (c: HTMLElement) => c.querySelector('svg > g') as SVGGElement

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(rectDe(CONTENEDOR, CONTENEDOR))
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('VistaSvg: render', () => {
  it('expone un SVG con role img y etiqueta en español', () => {
    render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    expect(svg().getAttribute('aria-label')).toMatch(/Vista previa del dibujo/)
  })

  it('pinta una entidad de cada tipo con el color y trazo de su capa', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    const lineas = container.querySelectorAll('line')
    const concreto = lineas[0]
    expect(concreto.getAttribute('stroke')).toBe('#f2f2f2')
    expect(concreto.getAttribute('stroke-width')).toBe('1.6')
    expect(concreto.getAttribute('vector-effect')).toBe('non-scaling-stroke')
    expect(concreto.getAttribute('stroke-dasharray')).toBeNull()

    expect(container.querySelector('circle[stroke="#f7d84a"]')).not.toBeNull()
    expect(container.querySelector('polygon[fill="#67d17c"]')).not.toBeNull()
  })

  it('el trazo EJE es discontinuo y el OCULTO es punteado', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    const eje = container.querySelector('line[stroke="#e05555"]')
    expect(eje?.getAttribute('stroke-dasharray')).toBe('4 2')
    const oculto = container.querySelector('path[stroke="#8a8f98"]')
    expect(oculto?.getAttribute('stroke-dasharray')).toBe('1 3')
  })

  it('el arco usa el path de pathArco en coordenadas de modelo', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    const d = pathArco(dibujo.render[2] as Parameters<typeof pathArco>[0])
    expect(container.querySelector(`path[d="${d}"]`)).not.toBeNull()
  })

  it('los textos llevan anclaje y contra-volteo; los demasiado pequeños se omiten', () => {
    const conCorto: DibujoJson = {
      ...dibujo,
      render: [
        ...dibujo.render,
        // Con escala 0.41, h=5 da 2.05 px (< 2.5): no se dibuja.
        { t: 'text', p: [10, 10], s: 'Corto', h: 5, rot: 0, l: 'TEXTOS', ha: 'l', va: 'b' },
      ],
    }
    const { container } = render(<VistaSvg dibujo={conCorto} capasOcultas={[]} />)
    const textos = Array.from(container.querySelectorAll('text'))
    expect(textos.map(t => t.textContent)).toEqual(['Texto'])
    const t = textos[0]
    expect(t.getAttribute('text-anchor')).toBe('middle')
    expect(t.getAttribute('dominant-baseline')).toBe('central')
    expect(t.getAttribute('transform')).toBe('translate(300 900) scale(1 -1)')
    expect(t.getAttribute('font-size')).toBe('20')
  })

  it('una capa desconocida se pinta en blanco', () => {
    const raro: DibujoJson = {
      ...dibujo,
      render: [{ t: 'line', a: [0, 0], b: [1, 1], l: 'RARO', w: 0 }],
    }
    const { container } = render(<VistaSvg dibujo={raro} capasOcultas={[]} />)
    expect(container.querySelector('line')?.getAttribute('stroke')).toBe('#ffffff')
  })

  it('oculta las capas indicadas', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={['CONCRETO']} />)
    expect(container.querySelector('line[stroke="#f2f2f2"]')).toBeNull()
    expect(container.querySelector('line[stroke="#e05555"]')).not.toBeNull()
  })

  it('acepta las capas ocultas como Set', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={new Set(['ACERO'])} />)
    expect(container.querySelector('circle[stroke="#f7d84a"]')).toBeNull()
  })

  it('aplica la transformación de encaje con inversión de Y', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    expect(raiz(container).getAttribute('transform')).toBe(T_AJUSTADA)
  })
})

describe('VistaSvg: vista', () => {
  it('cambiar dibujo conserva el zoom y el paneo', () => {
    const { container, rerender } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    fireEvent.wheel(svg(), { deltaY: -100, clientX: 250, clientY: 250 })
    const conZoom = raiz(container).getAttribute('transform')
    expect(conZoom).not.toBe(T_AJUSTADA)

    rerender(<VistaSvg dibujo={{ ...dibujo, render: dibujo.render.slice(1) }} capasOcultas={[]} />)
    expect(raiz(container).getAttribute('transform')).toBe(conZoom)
  })

  it('cambiar ajusteToken reajusta la vista', () => {
    const { container, rerender } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} ajusteToken={1} />)
    fireEvent.wheel(svg(), { deltaY: -100, clientX: 250, clientY: 250 })
    expect(raiz(container).getAttribute('transform')).not.toBe(T_AJUSTADA)

    rerender(<VistaSvg dibujo={dibujo} capasOcultas={[]} ajusteToken={2} />)
    expect(raiz(container).getAttribute('transform')).toBe(T_AJUSTADA)
  })

  it('la rueda hace zoom hacia el cursor y cancela el scroll de la página', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    const cursor = { clientX: 100, clientY: 400 }
    const antes = aModelo(VISTA_AJUSTADA, cursor.clientX, cursor.clientY, CONTENEDOR, CONTENEDOR)

    const noCancelado = fireEvent.wheel(svg(), { deltaY: -100, ...cursor })
    expect(noCancelado).toBe(false)

    // El punto de modelo bajo el cursor sigue bajo el cursor tras el zoom.
    const t = raiz(container).getAttribute('transform') ?? ''
    const m = /matrix\(([^ ]+) 0 0 ([^ ]+) ([^ ]+) ([^ ]+)\)/.exec(t)!
    const s = Number(m[1])
    const tx = Number(m[3])
    const ty = Number(m[4])
    const xPantalla = antes[0] * s + tx
    const yPantalla = antes[1] * -s + ty
    expect(xPantalla).toBeCloseTo(cursor.clientX, 2)
    expect(yPantalla).toBeCloseTo(cursor.clientY, 2)
  })

  it('arrastrar desplaza la vista; doble clic vuelve al ajuste', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    fireEvent.pointerDown(svg(), { clientX: 250, clientY: 250, button: 0, pointerId: 1 })
    fireEvent.pointerMove(svg(), { clientX: 300, clientY: 250, pointerId: 1 })
    fireEvent.pointerUp(svg(), { clientX: 300, clientY: 250, button: 0, pointerId: 1 })
    expect(raiz(container).getAttribute('transform')).not.toBe(T_AJUSTADA)

    fireEvent.doubleClick(svg())
    expect(raiz(container).getAttribute('transform')).toBe(T_AJUSTADA)
  })

  it('un clic corto sin modo medir no desplaza la vista', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} />)
    fireEvent.pointerDown(svg(), { clientX: 250, clientY: 250, button: 0, pointerId: 1 })
    fireEvent.pointerUp(svg(), { clientX: 251, clientY: 250, button: 0, pointerId: 1 })
    expect(raiz(container).getAttribute('transform')).toBe(T_AJUSTADA)
  })

  it('informa la posición del cursor en mm y null al salir', () => {
    const alCursor = vi.fn()
    render(<VistaSvg dibujo={dibujo} capasOcultas={[]} onCursor={alCursor} />)
    fireEvent.pointerMove(svg(), { clientX: 250, clientY: 250, pointerId: 1 })
    expect(alCursor).toHaveBeenLastCalledWith({ x: 500, y: 500 })
    fireEvent.pointerLeave(svg(), { pointerId: 1 })
    expect(alCursor).toHaveBeenLastCalledWith(null)
  })
})

describe('VistaSvg: modo medir', () => {
  const pantalla = (x: number, y: number) => aPantalla(VISTA_AJUSTADA, x, y, CONTENEDOR, CONTENEDOR)
  const clic = (p: [number, number]) => {
    fireEvent.pointerDown(svg(), { clientX: p[0], clientY: p[1], button: 0, pointerId: 7 })
    fireEvent.pointerUp(svg(), { clientX: p[0], clientY: p[1], button: 0, pointerId: 7 })
  }

  it('el snap muestra el círculo cerca de un extremo', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} modoMedir />)
    const [x, y] = pantalla(100, 200)
    fireEvent.pointerMove(svg(), { clientX: x + 2, clientY: y - 2, pointerId: 7 })
    expect(container.querySelector('.vista-svg__snap')).not.toBeNull()

    fireEvent.pointerMove(svg(), { clientX: 470, clientY: 30, pointerId: 7 })
    expect(container.querySelector('.vista-svg__snap')).toBeNull()
  })

  it('dos clics con snap dan la medida y llaman a onMedida', () => {
    const alMedir = vi.fn()
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} modoMedir onMedida={alMedir} />)
    // Puntos del dibujo (100,200) y (400,600), clicados con unos píxeles de error.
    const [x1, y1] = pantalla(100, 200)
    const [x2, y2] = pantalla(400, 600)
    clic([x1 + 2, y1 - 2])
    expect(alMedir).not.toHaveBeenCalled()
    clic([x2 - 2, y2 + 2])

    expect(alMedir).toHaveBeenCalledTimes(1)
    const medida = alMedir.mock.calls[0][0]
    expect(medida.dx).toBeCloseTo(300, 9)
    expect(medida.dy).toBeCloseTo(400, 9)
    expect(medida.dist).toBeCloseTo(500, 9)
    expect(medida.anguloDeg).toBeCloseTo((Math.atan2(400, 300) * 180) / Math.PI, 9)

    expect(container.querySelector('.vista-svg__medida')).not.toBeNull()
    expect(container.querySelector('.vista-svg__etiqueta')?.textContent).toContain('500 mm')
  })

  it('Escape cancela la medida en curso', () => {
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} modoMedir />)
    const [x1, y1] = pantalla(100, 200)
    clic([x1, y1])
    fireEvent.pointerMove(svg(), { clientX: 300, clientY: 300, pointerId: 7 })
    expect(container.querySelector('.vista-svg__medida')).not.toBeNull()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(container.querySelector('.vista-svg__medida')).toBeNull()
  })

  it('sin modo medir no se registran clics de medida', () => {
    const alMedir = vi.fn()
    render(<VistaSvg dibujo={dibujo} capasOcultas={[]} onMedida={alMedir} />)
    const [x1, y1] = pantalla(100, 200)
    const [x2, y2] = pantalla(400, 600)
    clic([x1, y1])
    clic([x2, y2])
    expect(alMedir).not.toHaveBeenCalled()
  })

  it('un arrastre en modo medir panea y no fija punto', () => {
    const alMedir = vi.fn()
    const { container } = render(<VistaSvg dibujo={dibujo} capasOcultas={[]} modoMedir onMedida={alMedir} />)
    fireEvent.pointerDown(svg(), { clientX: 250, clientY: 250, button: 0, pointerId: 3 })
    fireEvent.pointerMove(svg(), { clientX: 320, clientY: 250, pointerId: 3 })
    fireEvent.pointerUp(svg(), { clientX: 320, clientY: 250, button: 0, pointerId: 3 })
    expect(raiz(container).getAttribute('transform')).not.toBe(T_AJUSTADA)
    expect(alMedir).not.toHaveBeenCalled()
    expect(container.querySelector('.vista-svg__medida')).toBeNull()
  })
})
