// Exportación del dibujo a SVG autónomo (sin scripts ni recursos externos) y a PNG en el cliente.
import type { Caja, DibujoJson, EntRender } from '../tipos'
import {
  FONDO_VISOR,
  FUENTE_TEXTO,
  anchoTrazoPx,
  colorCapa,
  dashArray,
  toSet,
  type CapasOcultas,
  type Fondo,
} from './capas'
import { anclajeTexto, num, pathArco, pathPoligono, transformTexto } from './geometria'

export type OpcionesSvg = {
  capasOcultas?: CapasOcultas
  fondo?: Fondo
  margenMm?: number
}

/** 1 px a 96 ppp en milímetros: los anchos de la vista pasan a mm en el documento impreso. */
const PX_A_MM = 25.4 / 96

/**
 * SVG del dibujo con el viewBox en mm (bounds más margen). Se invierte Y con un <g>, igual
 * que el visor, y los textos se contra-voltean para no salir en espejo.
 */
export function aSvg(dibujo: DibujoJson, opciones: OpcionesSvg = {}): string {
  const fondo: Fondo = opciones.fondo ?? 'claro'
  const margen = opciones.margenMm ?? 10
  const ocultas = toSet(opciones.capasOcultas ?? [])
  const [x0, y0, x1, y1]: Caja = dibujo.bounds ?? [-50, -50, 50, 50]
  const ancho = x1 - x0 + 2 * margen
  const alto = y1 - y0 + 2 * margen
  const vx = x0 - margen
  const vy = -(y1 + margen) // coordenadas tras el flip de Y

  const contenido = dibujo.render
    .filter(e => !ocultas.has(e.l))
    .map(e => elemento(e, fondo))
    .join('')
  const fondoRect = fondo === 'claro' ? '#ffffff' : FONDO_VISOR

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${num(ancho)}mm" height="${num(alto)}mm"` +
    ` viewBox="${num(vx)} ${num(vy)} ${num(ancho)} ${num(alto)}">` +
    `<rect x="${num(vx)}" y="${num(vy)}" width="${num(ancho)}" height="${num(alto)}"` +
    ` fill="${fondoRect}"/>` +
    `<g transform="scale(1 -1)">${contenido}</g>` +
    '</svg>'
  )
}

function elemento(e: EntRender, fondo: Fondo): string {
  const color = colorCapa(e.l, fondo)
  const trazo = (anchoPx: number): string => {
    const w = anchoPx * PX_A_MM
    const d = dashArray(e.l, w)
    return `fill="none" stroke="${color}" stroke-width="${num(w)}"` + (d ? ` stroke-dasharray="${d}"` : '')
  }
  switch (e.t) {
    case 'line':
      return (
        `<line x1="${num(e.a[0])}" y1="${num(e.a[1])}" x2="${num(e.b[0])}" y2="${num(e.b[1])}" ` +
        `${trazo(anchoTrazoPx(e.l, e.w))}/>`
      )
    case 'circle':
      if (e.f) {
        return `<circle cx="${num(e.c[0])}" cy="${num(e.c[1])}" r="${num(e.r)}" fill="${color}" stroke="none"/>`
      }
      return `<circle cx="${num(e.c[0])}" cy="${num(e.c[1])}" r="${num(e.r)}" ${trazo(anchoTrazoPx(e.l))}/>`
    case 'arc':
      return `<path d="${pathArco(e)}" ${trazo(anchoTrazoPx(e.l))}/>`
    case 'poly':
      if (e.p.length === 0) return ''
      return `<path d="${pathPoligono(e.p, e.z)}" ${trazo(anchoTrazoPx(e.l, e.w))}/>`
    case 'filled':
      if (e.p.length === 0) return ''
      return `<polygon points="${e.p.map(p => `${num(p[0])},${num(p[1])}`).join(' ')}" fill="${color}" stroke="none"/>`
    case 'text': {
      if (!(e.h > 0)) return ''
      const an = anclajeTexto(e.ha, e.va)
      return (
        `<text transform="${transformTexto(e.p, e.rot)}" font-size="${num(e.h)}"` +
        ` font-family="${FUENTE_TEXTO}" fill="${color}" text-anchor="${an.textAnchor}"` +
        ` dominant-baseline="${an.dominantBaseline}">${escapar(e.s)}</text>`
      )
    }
  }
}

function escapar(texto: string): string {
  return texto
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

/** Rasteriza un SVG a PNG de `anchoPx` píxeles de ancho. Solo funciona en el navegador. */
export async function aPngBlob(svg: string, anchoPx: number): Promise<Blob> {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  try {
    const img = await new Promise<HTMLImageElement>((resolver, rechazar) => {
      const im = new Image()
      im.onload = () => resolver(im)
      im.onerror = () => rechazar(new Error('No se pudo cargar el SVG para exportar'))
      im.src = url
    })
    const ancho = Math.round(anchoPx)
    const alto = Math.round(anchoPx * (img.naturalHeight / img.naturalWidth))
    const lienzo = document.createElement('canvas')
    lienzo.width = ancho
    lienzo.height = alto
    const ctx = lienzo.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D no disponible')
    ctx.drawImage(img, 0, 0, ancho, alto)
    return await new Promise<Blob>((resolver, rechazar) => {
      lienzo.toBlob(b => (b ? resolver(b) : rechazar(new Error('No se pudo generar el PNG'))), 'image/png')
    })
  } finally {
    URL.revokeObjectURL(url)
  }
}
