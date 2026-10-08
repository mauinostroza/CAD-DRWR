// Geometría pura del visor SVG: vista (zoom y paneo), transformaciones, arcos, anclajes,
// snaps y medidas. Convención: modelo en mm con Y hacia arriba; pantalla en px con Y hacia abajo.
import type { Caja, EntArco, EntRender, EntTexto, Punto } from '../tipos'

export type Vista = { escala: number; cx: number; cy: number }
export type Medida = { dx: number; dy: number; dist: number; anguloDeg: number }
export type AnclajeTexto = {
  textAnchor: 'start' | 'middle' | 'end'
  dominantBaseline: 'text-before-edge' | 'central' | 'text-after-edge'
}

const ESCALA_MIN = 1e-4
const FACTOR_ZOOM = 1.15

/** Número con hasta 6 decimales y sin "-0", para atributos SVG compactos. */
export function num(v: number): string {
  const r = Math.round(v * 1e6) / 1e6
  return r === 0 ? '0' : String(r)
}

/** Vista que encaja la caja en el área, con margen en px. Sin caja: escala 0.2 centrada en 0,0. */
export function ajustarVista(bounds: Caja | null, ancho: number, alto: number, margen = 90): Vista {
  if (!bounds) return { escala: 0.2, cx: 0, cy: 0 }
  const [x0, y0, x1, y1] = bounds
  const w = Math.max(x1 - x0, 1)
  const h = Math.max(y1 - y0, 1)
  const escala = Math.max(Math.min((ancho - margen) / w, (alto - margen) / h), ESCALA_MIN)
  return { escala, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 }
}

/**
 * Zoom 1.15^delta manteniendo fijo el punto de modelo bajo el cursor (px, py).
 * El cambio de escala se acota a [old*1e-4, old*1e4] en cada paso, como en preview.py.
 */
export function zoomHaciaCursor(
  v: Vista,
  delta: number,
  px: number,
  py: number,
  ancho: number,
  alto: number,
): Vista {
  if (Math.abs(delta) < 1e-6) return v
  const viejo = v.escala
  const nueva = Math.max(Math.min(viejo * FACTOR_ZOOM ** delta, viejo * 1e4), viejo * 1e-4)
  const mmx = v.cx + (px - ancho / 2) / viejo
  const mmy = v.cy - (py - alto / 2) / viejo
  return {
    escala: nueva,
    cx: mmx - (px - ancho / 2) / nueva,
    cy: mmy + (py - alto / 2) / nueva,
  }
}

/** Modelo -> pantalla: X = (x - cx) * s + W/2, Y = H/2 - (y - cy) * s. */
export function aPantalla(v: Vista, x: number, y: number, ancho: number, alto: number): Punto {
  return [(x - v.cx) * v.escala + ancho / 2, alto / 2 - (y - v.cy) * v.escala]
}

/** Pantalla -> modelo (inversa de aPantalla). */
export function aModelo(v: Vista, px: number, py: number, ancho: number, alto: number): Punto {
  return [v.cx + (px - ancho / 2) / v.escala, v.cy - (py - alto / 2) / v.escala]
}

/** Atributo transform del <g> raíz: matriz de modelo a pantalla con la inversión de Y. */
export function transformacion(v: Vista, ancho: number, alto: number): string {
  const tx = ancho / 2 - v.cx * v.escala
  const ty = alto / 2 + v.cy * v.escala
  return `matrix(${num(v.escala)} 0 0 ${num(-v.escala)} ${num(tx)} ${num(ty)})`
}

/**
 * Barrido firmado del arco en grados, igual que _sweep de preview.py:
 * ccw -> (a2 - a1) mod 360 (360 si es 0); no ccw -> negativo.
 */
export function barridoArco(a: Pick<EntArco, 'a1' | 'a2' | 'ccw'>): number {
  const mod360 = (g: number) => ((g % 360) + 360) % 360
  if (a.ccw) return mod360(a.a2 - a.a1) || 360
  return -(mod360(a.a1 - a.a2) || 360)
}

/**
 * Path SVG del arco en coordenadas de modelo (Y arriba). El path va sin invertir: el flip
 * lo aplica el <g> padre, así que el flag de barrido es directo (1 si el barrido es
 * positivo, es decir, antihorario en modelo). El flag large-arc es |barrido| > 180.
 * Un barrido de 360 se parte en dos semiarcos, porque un arco SVG con extremos iguales no se dibuja.
 */
export function pathArco(a: EntArco): string {
  const r = a.r
  if (!(r > 0)) return `M ${num(a.c[0])} ${num(a.c[1])}`
  const punto = (deg: number): Punto => {
    const t = (deg * Math.PI) / 180
    return [a.c[0] + r * Math.cos(t), a.c[1] + r * Math.sin(t)]
  }
  const s = barridoArco(a)
  const sf = s > 0 ? 1 : 0
  const [x0, y0] = punto(a.a1)
  if (Math.abs(s) >= 360 - 1e-9) {
    const [xm, ym] = punto(a.a1 + s / 2)
    return (
      `M ${num(x0)} ${num(y0)} A ${num(r)} ${num(r)} 0 0 ${sf} ${num(xm)} ${num(ym)}` +
      ` A ${num(r)} ${num(r)} 0 0 ${sf} ${num(x0)} ${num(y0)} Z`
    )
  }
  const [x1, y1] = punto(a.a1 + s)
  const large = Math.abs(s) > 180 ? 1 : 0
  return `M ${num(x0)} ${num(y0)} A ${num(r)} ${num(r)} 0 ${large} ${sf} ${num(x1)} ${num(y1)}`
}

/** Path de una polilínea o polígono cerrado en modelo. */
export function pathPoligono(pts: readonly Punto[], cerrado: boolean): string {
  if (pts.length === 0) return ''
  const partes = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${num(p[0])} ${num(p[1])}`)
  return partes.join(' ') + (cerrado ? ' Z' : '')
}

/**
 * Transform de un texto dentro del <g> con flip: el texto queda sin espejo y con la
 * rotación antihoraria `rot` vista en pantalla (equivale a rotate(-rot) en el espacio con flip).
 */
export function transformTexto(p: Punto, rot: number): string {
  const base = `translate(${num(p[0])} ${num(p[1])}) scale(1 -1)`
  return rot ? `${base} rotate(${num(-rot)})` : base
}

/** Anclaje SVG equivalente a ALIGN_H / ALIGN_V de preview.py. */
export function anclajeTexto(ha: EntTexto['ha'], va: EntTexto['va']): AnclajeTexto {
  const textAnchor = ha === 'l' ? 'start' : ha === 'r' ? 'end' : 'middle'
  const dominantBaseline = va === 'b' ? 'text-after-edge' : va === 't' ? 'text-before-edge' : 'central'
  return { textAnchor, dominantBaseline }
}

/** Puntos candidatos a snap: extremos de línea y polilínea, puntos medios de línea, centros. */
function* candidatosSnap(render: readonly EntRender[]): Generator<Punto> {
  for (const e of render) {
    switch (e.t) {
      case 'line':
        yield e.a
        yield e.b
        yield [(e.a[0] + e.b[0]) / 2, (e.a[1] + e.b[1]) / 2]
        break
      case 'poly':
        yield* e.p
        break
      case 'circle':
      case 'arc':
        yield e.c
        break
      default:
        break
    }
  }
}

/**
 * Punto de snap más cercano a `p` dentro de `tolPx` píxeles de pantalla, o null.
 * La tolerancia se convierte a mm con la escala actual.
 */
export function snaps(render: readonly EntRender[], tolPx: number, escala: number, p: Punto): Punto | null {
  const tol = tolPx / escala
  let mejor: Punto | null = null
  let mejorDist = Infinity
  for (const q of candidatosSnap(render)) {
    const d = Math.hypot(q[0] - p[0], q[1] - p[1])
    if (d <= tol && d < mejorDist) {
      mejorDist = d
      mejor = q
    }
  }
  return mejor
}

/** Medida entre dos puntos de modelo. El ángulo va de 0 a 360 grados, antihorario desde +X. */
export function medir(p1: Punto, p2: Punto): Medida {
  const dx = p2[0] - p1[0]
  const dy = p2[1] - p1[1]
  let anguloDeg = (Math.atan2(dy, dx) * 180) / Math.PI
  if (anguloDeg < 0) anguloDeg += 360
  return { dx, dy, dist: Math.hypot(dx, dy), anguloDeg }
}
