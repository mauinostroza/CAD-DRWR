// Tipos del módulo CAD-DRWR (StructGenCAD en la web). Unidades de la IR: mm, eje Y hacia arriba.

export type Punto = [number, number]

/** Capas de la IR (mismos nombres que el DXF). */
export type Capa =
  | 'EJE'
  | 'CONCRETO'
  | 'ACERO'
  | 'ACOTADO'
  | 'TEXTOS'
  | 'PERFORACIONES'
  | 'SOLDADURA'
  | 'HACHURADO'
  | 'TABLAS'
  | 'OCULTO'

export type EntLinea = { t: 'line'; a: Punto; b: Punto; l: string; w: number }
export type EntCirculo = { t: 'circle'; c: Punto; r: number; l: string; f: boolean }
export type EntArco = {
  t: 'arc'
  c: Punto
  r: number
  a1: number
  a2: number
  ccw: boolean
  l: string
}
export type EntPoli = { t: 'poly'; p: Punto[]; z: boolean; l: string; w: number }
export type EntRelleno = { t: 'filled'; p: Punto[]; l: string }
export type EntTexto = {
  t: 'text'
  p: Punto
  s: string
  h: number
  rot: number
  l: string
  ha: 'l' | 'c' | 'r'
  va: 'b' | 'm' | 't'
}
export type EntCota = {
  t: 'dim'
  a: Punto
  b: Punto
  base: Punto
  v: boolean
  l: string
  txt: string | null
  th: number
}

/** Primitivas que el visor SVG sabe pintar (la cota ya viene descompuesta). */
export type EntRender = EntLinea | EntCirculo | EntArco | EntPoli | EntRelleno | EntTexto
/** Entidades para el CAD: igual que render, pero con cotas nativas. */
export type EntCad = EntRender | EntCota

export type Caja = [number, number, number, number] // x0, y0, x1, y1

export type DibujoJson = {
  th: number
  bounds: Caja | null
  render: EntRender[]
  cad: EntCad[]
  n_render: number
  n_cad: number
}

export type CampoCombo = {
  key: string
  label: string
  kind: 'combo'
  options: string[]
  value: string
}
export type CampoInt = {
  key: string
  label: string
  kind: 'int'
  min: number
  max: number
  value: number
  step: number
  suffix: string
}
export type CampoFloat = {
  key: string
  label: string
  kind: 'float'
  min: number
  max: number
  value: number
  decimals: number
  step: number
  suffix: string
}
export type CampoChk = { key: string; label: string; kind: 'chk'; value: boolean }
export type Campo = CampoCombo | CampoInt | CampoFloat | CampoChk

export type ParamValor = string | number | boolean
export type Params = Record<string, ParamValor>

export type ModuloInfo = {
  id: string
  nombre: string
  campos: Campo[]
  defaults: Params
  /** Módulo con panel interactivo propio (Fundación SAP2000): sin formulario declarativo. */
  interactivo: boolean
}

export type Lamina = {
  activa: boolean
  proyecto: string
  numero_plano: string
  revision: string
}

export type EstadoModulo = {
  disponible: boolean
  detalle: string
  motor: string
  limites: { entidades: number; zapatas: number; puntos: number; lote_zip: number }
}
