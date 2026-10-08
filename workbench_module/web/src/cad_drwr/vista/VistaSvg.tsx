// Visor SVG del dibujo: zoom hacia el cursor, paneo, ajuste y medida con snap.
import {
  memo,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactElement,
  type ReactNode,
} from 'react'
import type { DibujoJson, EntRender, Punto } from '../tipos'
import {
  FONDO_VISOR,
  FUENTE_TEXTO,
  anchoTrazoPx,
  colorCapa,
  dashArray,
  toSet,
  type CapasOcultas,
} from './capas'
import {
  ajustarVista,
  aModelo,
  aPantalla,
  anclajeTexto,
  medir,
  pathArco,
  pathPoligono,
  snaps,
  transformacion,
  transformTexto,
  zoomHaciaCursor,
  type Medida,
  type Vista,
} from './geometria'
import './vista.css'

export type VistaSvgProps = {
  dibujo: DibujoJson
  capasOcultas: CapasOcultas
  /** Cambiar este valor reajusta la vista a la caja del dibujo. */
  ajusteToken?: string | number
  modoMedir?: boolean
  onMedida?: (medida: Medida) => void
  /** Posición del cursor en mm (modelo), o null al salir del visor. */
  onCursor?: (p: { x: number; y: number } | null) => void
}

type Arrastre = {
  id: number
  x0: number
  y0: number
  ux: number
  uy: number
  movido: boolean
}

type Sobre = { punto: Punto; snap: Punto | null }

/** Textos con altura en mm por debajo de este tamaño en píxeles no se dibujan. */
const UMBRAL_TEXTO_PX = 2.5
const ARRASTRE_MIN_PX = 4
const TOLERANCIA_SNAP_PX = 10
/** Píxeles de deltaY por muesca de rueda (Qt usa 120 unidades; el navegador suele reportar 100). */
const PX_POR_MUESCA = 100
const ETIQUETA =
  'Vista previa del dibujo estructural: rueda para zoom, arrastre para desplazar y doble clic para ajustar'
const FORMATO = new Intl.NumberFormat('es', { maximumFractionDigits: 1 })

/** Primer índice de `ordenados` cuyo valor es >= v (búsqueda binaria). */
function primeraNoMenor(ordenados: readonly number[], v: number): number {
  let lo = 0
  let hi = ordenados.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (ordenados[mid] < v) lo = mid + 1
    else hi = mid
  }
  return lo
}

/**
 * Entidad del dibujo. Memoizada: con la vista cambiando (zoom o paneo) sus props no cambian
 * y React no la vuelve a renderizar.
 */
const EntidadSvg = memo(function EntidadSvg({ ent }: { ent: EntRender }): ReactElement | null {
  const color = colorCapa(ent.l, 'oscuro')
  switch (ent.t) {
    case 'line': {
      const w = anchoTrazoPx(ent.l, ent.w)
      return (
        <line
          x1={ent.a[0]}
          y1={ent.a[1]}
          x2={ent.b[0]}
          y2={ent.b[1]}
          stroke={color}
          strokeWidth={w}
          strokeDasharray={dashArray(ent.l, w)}
          vectorEffect="non-scaling-stroke"
        />
      )
    }
    case 'circle': {
      if (ent.f) {
        return <circle cx={ent.c[0]} cy={ent.c[1]} r={ent.r} fill={color} stroke="none" />
      }
      const w = anchoTrazoPx(ent.l)
      return (
        <circle
          cx={ent.c[0]}
          cy={ent.c[1]}
          r={ent.r}
          fill="none"
          stroke={color}
          strokeWidth={w}
          strokeDasharray={dashArray(ent.l, w)}
          vectorEffect="non-scaling-stroke"
        />
      )
    }
    case 'arc': {
      const w = anchoTrazoPx(ent.l)
      return (
        <path
          d={pathArco(ent)}
          fill="none"
          stroke={color}
          strokeWidth={w}
          strokeDasharray={dashArray(ent.l, w)}
          vectorEffect="non-scaling-stroke"
        />
      )
    }
    case 'poly': {
      if (ent.p.length === 0) return null
      const w = anchoTrazoPx(ent.l, ent.w)
      return (
        <path
          d={pathPoligono(ent.p, ent.z)}
          fill="none"
          stroke={color}
          strokeWidth={w}
          strokeDasharray={dashArray(ent.l, w)}
          vectorEffect="non-scaling-stroke"
        />
      )
    }
    case 'filled': {
      if (ent.p.length === 0) return null
      const puntos = ent.p.map(p => `${p[0]},${p[1]}`).join(' ')
      return <polygon points={puntos} fill={color} stroke="none" />
    }
    case 'text': {
      // El texto va en espacio con flip y se contra-voltea: no sale en espejo.
      const an = anclajeTexto(ent.ha, ent.va)
      return (
        <text
          transform={transformTexto(ent.p, ent.rot)}
          x={0}
          y={0}
          fontSize={ent.h}
          fontFamily={FUENTE_TEXTO}
          fill={color}
          textAnchor={an.textAnchor}
          dominantBaseline={an.dominantBaseline}
        >
          {ent.s}
        </text>
      )
    }
  }
})

export function VistaSvg({
  dibujo,
  capasOcultas,
  ajusteToken,
  modoMedir = false,
  onMedida,
  onCursor,
}: VistaSvgProps): ReactElement {
  const contenedor = useRef<HTMLDivElement>(null)
  const dibujoRef = useRef(dibujo)
  const medidoRef = useRef(false)
  const arrastreRef = useRef<Arrastre | null>(null)
  const [vista, setVista] = useState<Vista>({ escala: 0.2, cx: 0, cy: 0 })
  const [tam, setTam] = useState({ ancho: 0, alto: 0 })
  const [arrastrando, setArrastrando] = useState(false)
  const [puntos, setPuntos] = useState<Punto[]>([])
  const [sobre, setSobre] = useState<Sobre | null>(null)

  useLayoutEffect(() => {
    dibujoRef.current = dibujo
  })

  /** Mide el contenedor y ajusta la vista a la caja del dibujo (solo con tamaño válido). */
  const ajustar = (): void => {
    const el = contenedor.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setTam({ ancho: r.width, alto: r.height })
    if (r.width <= 0 || r.height <= 0) return
    setVista(ajustarVista(dibujoRef.current.bounds, r.width, r.height))
    medidoRef.current = true
  }

  // Ajuste al montar y cada vez que cambia ajusteToken.
  useLayoutEffect(() => {
    ajustar()
  }, [ajusteToken])

  // Tamaño del contenedor. Al crecer desde 0 (p. ej. en una pestaña oculta) se ajusta una vez.
  useLayoutEffect(() => {
    const el = contenedor.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => {
      if (!medidoRef.current) {
        ajustar()
        return
      }
      const r = el.getBoundingClientRect()
      setTam({ ancho: r.width, alto: r.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Rueda: zoom hacia el cursor. Listener no pasivo para poder cancelar el scroll de la página.
  useEffect(() => {
    const el = contenedor.current
    if (!el) return
    const alRueda = (e: WheelEvent): void => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const dy = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaMode === 2 ? e.deltaY * 800 : e.deltaY
      const delta = -dy / PX_POR_MUESCA
      const px = e.clientX - r.left
      const py = e.clientY - r.top
      setVista(v => zoomHaciaCursor(v, delta, px, py, r.width, r.height))
    }
    el.addEventListener('wheel', alRueda, { passive: false })
    return () => el.removeEventListener('wheel', alRueda)
  }, [])

  // Escape cancela la medida en curso.
  useEffect(() => {
    if (!modoMedir) return
    const alTecla = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') setPuntos([])
    }
    window.addEventListener('keydown', alTecla)
    return () => window.removeEventListener('keydown', alTecla)
  }, [modoMedir])

  const localDe = (e: { clientX: number; clientY: number }) => {
    const r = contenedor.current?.getBoundingClientRect()
    return {
      px: e.clientX - (r?.left ?? 0),
      py: e.clientY - (r?.top ?? 0),
      ancho: r?.width ?? tam.ancho,
      alto: r?.height ?? tam.alto,
    }
  }

  const alBajar = (e: ReactPointerEvent<SVGSVGElement>): void => {
    if (e.button !== 0) return
    arrastreRef.current = {
      id: e.pointerId,
      x0: e.clientX,
      y0: e.clientY,
      ux: e.clientX,
      uy: e.clientY,
      movido: false,
    }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const alMover = (e: ReactPointerEvent<SVGSVGElement>): void => {
    const a = arrastreRef.current
    if (a && a.id === e.pointerId) {
      if (!a.movido && Math.hypot(e.clientX - a.x0, e.clientY - a.y0) > ARRASTRE_MIN_PX) {
        a.movido = true
        setArrastrando(true)
      }
      if (a.movido) {
        const dxPx = e.clientX - a.ux
        const dyPx = e.clientY - a.uy
        a.ux = e.clientX
        a.uy = e.clientY
        setVista(v => ({ ...v, cx: v.cx - dxPx / v.escala, cy: v.cy + dyPx / v.escala }))
      }
    }
    const { px, py, ancho, alto } = localDe(e)
    const m = aModelo(vista, px, py, ancho, alto)
    onCursor?.({ x: m[0], y: m[1] })
    if (modoMedir && !a?.movido) {
      setSobre({ punto: m, snap: snaps(dibujo.render, TOLERANCIA_SNAP_PX, vista.escala, m) })
    }
  }

  const alSoltar = (e: ReactPointerEvent<SVGSVGElement>): void => {
    const a = arrastreRef.current
    arrastreRef.current = null
    setArrastrando(false)
    // Solo un clic (sin arrastre) fija un punto de medida.
    if (!a || a.id !== e.pointerId || a.movido || !modoMedir) return
    const { px, py, ancho, alto } = localDe(e)
    const m = aModelo(vista, px, py, ancho, alto)
    const p = snaps(dibujo.render, TOLERANCIA_SNAP_PX, vista.escala, m) ?? m
    if (puntos.length === 1) {
      const medida = medir(puntos[0], p)
      setPuntos([puntos[0], p])
      onMedida?.(medida)
    } else {
      setPuntos([p])
    }
  }

  const alSalir = (): void => {
    setSobre(null)
    onCursor?.(null)
  }

  // Alturas de texto distintas, ordenadas. Un texto se omite si su altura en píxeles es menor
  // que UMBRAL_TEXTO_PX. Como el criterio depende solo del índice de este umbral, la lista de
  // entidades cambia solo cuando cambia el conjunto de textos visibles, no en cada zoom.
  const alturasTexto = useMemo(() => {
    const s = new Set<number>()
    for (const e of dibujo.render) if (e.t === 'text') s.add(e.h)
    return [...s].sort((a, b) => a - b)
  }, [dibujo])
  const umbralTexto = useMemo(() => {
    const idx = primeraNoMenor(alturasTexto, UMBRAL_TEXTO_PX / vista.escala)
    return idx < alturasTexto.length ? alturasTexto[idx] : Infinity
  }, [alturasTexto, vista.escala])

  const capas = useMemo(() => toSet(capasOcultas), [capasOcultas])

  // Lista de entidades. Depende del dibujo, de las capas ocultas y del umbral de texto,
  // nunca del paneo ni del zoom en sí: por eso el paneo no recalcula nada.
  const elementos = useMemo(() => {
    const out: ReactNode[] = []
    dibujo.render.forEach((e, i) => {
      if (capas.has(e.l)) return
      if (e.t === 'text' && !(e.h >= umbralTexto)) return
      out.push(<EntidadSvg key={i} ent={e} />)
    })
    return out
  }, [dibujo, capas, umbralTexto])

  const { ancho, alto } = tam
  const pantalla = (p: Punto): Punto => aPantalla(vista, p[0], p[1], ancho, alto)

  // Superposición de medida, en pantalla (no se escala con el zoom).
  let trazo: [Punto, Punto] | null = null
  let medida: Medida | null = null
  if (modoMedir && puntos.length === 2) {
    trazo = [puntos[0], puntos[1]]
    medida = medir(puntos[0], puntos[1])
  } else if (modoMedir && puntos.length === 1 && sobre) {
    trazo = [puntos[0], sobre.snap ?? sobre.punto]
  }
  const snapVisible = modoMedir && sobre?.snap ? pantalla(sobre.snap) : null
  const trazoPx = trazo ? [pantalla(trazo[0]), pantalla(trazo[1])] : null

  return (
    <div
      ref={contenedor}
      className={
        'vista-svg' + (arrastrando ? ' vista-svg--arrastrando' : '') + (modoMedir ? ' vista-svg--medir' : '')
      }
    >
      <svg
        role="img"
        aria-label={ETIQUETA}
        className="vista-svg__lienzo"
        onPointerDown={alBajar}
        onPointerMove={alMover}
        onPointerUp={alSoltar}
        onPointerCancel={alSoltar}
        onPointerLeave={alSalir}
        onDoubleClick={ajustar}
      >
        <rect width="100%" height="100%" fill={FONDO_VISOR} />
        <g transform={transformacion(vista, ancho, alto)} pointerEvents="none">
          {elementos}
        </g>
        {trazoPx && (
          <g pointerEvents="none">
            <line
              className="vista-svg__medida"
              x1={trazoPx[0][0]}
              y1={trazoPx[0][1]}
              x2={trazoPx[1][0]}
              y2={trazoPx[1][1]}
              stroke="#ffd166"
              strokeWidth={1.5}
            />
            {medida && (
              <text
                className="vista-svg__etiqueta"
                x={trazoPx[1][0] + 8}
                y={trazoPx[1][1] - 8}
                fill="#ffd166"
                fontSize={12}
                fontFamily={FUENTE_TEXTO}
              >
                {`${FORMATO.format(medida.dist)} mm · ${FORMATO.format(medida.anguloDeg)}°`}
              </text>
            )}
          </g>
        )}
        {snapVisible && (
          <circle
            className="vista-svg__snap"
            cx={snapVisible[0]}
            cy={snapVisible[1]}
            r={6}
            fill="none"
            stroke="#ffd166"
            strokeWidth={1.5}
            pointerEvents="none"
          />
        )}
      </svg>
    </div>
  )
}
