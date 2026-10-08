// Porte mecánico de backend/motor_calculo/cad_drwr/generators/reglas_ui.py y de los
// autollenar de base_plate, profile y anchor_bolt. El golden que manda es
// backend/motor_calculo/cad_drwr/golden/reglas_ui.json.
import { HE_DB, W_DB, type Tabla } from './catalogos'
import type { ParamValor, Params } from './tipos'

type Dimensiones = { d: number; bf: number; tw: number; tf: number }
type Regla = (estado: Params) => Record<string, boolean>
type Autollenado = (p: Params, campo: string) => Params

const PRESET_DEFAULT = 'Total anterior'
const PRESET_REF20 = 'Referencia 20'

/** Valores que el bloque "Referencia 20" del Panel fija al ENTRAR a ese modo. */
const REF20_VALORES: Params = {
  b: 55,
  h: 40,
  r: 5,
  d_barra: '16',
  d_estribo: '10',
  e_estribo: 15,
  lazos_interiores: true,
  lazo_vertical: true,
  lazo_horizontal: true,
  elevacion: false,
  cuadro: false,
}

/**
 * Defaults de cada SPEC (SpecPanel.__init__) de los módulos con reglas. Generado
 * con reglas_ui._defaults() para no transcribir a mano. Las claves son las del SPEC.
 */
const DEFAULTS_UI: Record<string, Params> = {
  placa_base: {
    perfil: 'W250X25',
    d: 257,
    bf: 101,
    tw: 5.8,
    tf: 8.4,
    B: 440,
    N: 590,
    w_conc: 640,
    t: 12,
    n_pernos: '4',
    d_perno: '19',
    g: 345,
    p: 495,
    P: 100,
    Le: 450,
    cartelas: true,
    hs: 150,
    ls: 80,
    ts: 12,
    w_sold: 8,
    detalle_perno: true,
    tabla_pernos: true,
    material_placa: 'No especificado',
    material_perno: 'No especificado',
    grout_mpa: 0,
    norma_soldadura: 'No especificada',
    escala: '1:50',
  },
  pedestal: {
    b: 30,
    h: 30,
    H: 250,
    r: 4,
    n_barras: '8',
    preset: 'Total anterior',
    n_sup: 7,
    n_inf: 7,
    n_izq: 3,
    n_der: 3,
    lazos_interiores: false,
    lazo_vertical: true,
    lazo_horizontal: true,
    cuadro: true,
    d_barra: '18',
    d_estribo: '8',
    e_estribo: 15,
    elevacion: true,
    ancho_zap: 130,
    alto_zap: 30,
    r_zapata: 50,
    traslape: 45,
    gancho_arranque: 90,
    largo_barra: 3.2,
    modo_b1: 'Según elevación',
    fc: 21,
    fy: 420,
    escala: '1:25',
  },
  losa: {
    L: 400,
    t: 15,
    bw: 20,
    hh: 40,
    r: 3,
    ancho_reparto: 300,
    d1: '12',
    s1: 20,
    d2: '8',
    s2: 25,
    sup: true,
    d3: '10',
    s3: 15,
    a: 60,
    gv: 15,
    escala: '1:50',
  },
  perno_anclaje: {
    d_perno: '25.4',
    d_nominal: '1 in',
    tipo: 'PG (recto con golilla)',
    Le: 850,
    P: 400,
    lg: 150,
    tipo_hilo: '8UN',
    h1: 150,
    h2: 75,
    W: 75,
    t_golilla: 20,
    b_golilla: 50,
    permitir_h1_bajo_tc: false,
    material: 'A307',
    acabado: 'Por definir',
    n: 48,
    tabla: true,
    escala: '1:25',
  },
  perfil: {
    tipo: 'Perfil I / W',
    serie: 'W250X25',
    d: 257,
    bf: 101,
    tw: 5.8,
    tf: 8.4,
    escala: '1:20',
  },
  forma_barra: {
    forma: 'U',
    a: 600,
    b: 300,
    c: 200,
    d_barra: '12',
    k: 4,
    qty: 10,
    marca: 'B1',
    escala: '1:25',
  },
}

/** Módulos con reglas de interfaz (fundacion_sap es interactivo y no aplica). */
export function soportaModulo(moduloId: string): boolean {
  return Object.hasOwn(DEFAULTS_UI, moduloId)
}

function exigirModulo(moduloId: string): Params {
  if (!Object.hasOwn(DEFAULTS_UI, moduloId)) {
    throw new Error(`módulo sin reglas de interfaz: '${moduloId}'`)
  }
  return DEFAULTS_UI[moduloId]
}

/** "Legacy" se trata como "Total anterior" (PedestalPanel). */
function presetEfectivo(valor: ParamValor | undefined): ParamValor | undefined {
  return valor === 'Legacy' ? PRESET_DEFAULT : valor
}

/** Igualdad de valores de widget: numérica con tolerancia 1e-9, resto exacta. */
function igual(a: ParamValor | undefined, b: ParamValor): boolean {
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) <= 1e-9
  return a === b
}

/**
 * Escala "1:n" -> n/10. Si no parsea, 5 (igual que factor_escala). Python toma
 * split(":")[1]; aquí se exige que ese segundo tramo sea un número decimal.
 */
const RE_DECIMAL = /^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\s*$/
export function factorEscala(escala: string): number {
  const n = escala.split(':')[1]
  if (n === undefined || !RE_DECIMAL.test(n)) return 5
  return Number(n) / 10
}

// --------------------------------------------------------- habilitados --
function habPedestal(v: Params): Record<string, boolean> {
  const preset = presetEfectivo(v.preset)
  const porCaras = preset === 'Por caras'
  const lazos = Boolean(v.lazos_interiores)
  return {
    largo_barra: v.modo_b1 !== 'Según elevación',
    n_barras: preset === PRESET_DEFAULT,
    lazo_vertical: lazos,
    lazo_horizontal: lazos,
    n_sup: porCaras,
    n_inf: porCaras,
    n_izq: porCaras,
    n_der: porCaras,
  }
}

function habPerno(v: Params): Record<string, boolean> {
  const pg = String(v.tipo).startsWith('PG')
  const inch = pg && v.d_nominal === '1 in'
  const out: Record<string, boolean> = { d_perno: !inch, lg: !pg }
  for (const clave of [
    'd_nominal',
    'h1',
    'h2',
    'W',
    't_golilla',
    'b_golilla',
    'permitir_h1_bajo_tc',
  ]) {
    out[clave] = pg
  }
  return out
}

const REGLAS_HABILITADOS: Record<string, Regla> = {
  pedestal: habPedestal,
  perno_anclaje: habPerno,
}

/** Para cada clave del SPEC, si el widget del Panel original queda habilitado. */
export function habilitados(moduloId: string, p: Params): Record<string, boolean> {
  const defaults = exigirModulo(moduloId)
  const estado: Params = { ...defaults, ...p }
  const out: Record<string, boolean> = {}
  for (const clave of Object.keys(defaults)) out[clave] = true
  if (Object.hasOwn(REGLAS_HABILITADOS, moduloId)) {
    Object.assign(out, REGLAS_HABILITADOS[moduloId](estado))
  }
  return out
}

// ---------------------------------------------------------- autollenado --
/** Devuelve solo las claves de d/bf/tw/tf que difieren de p. */
function cambiosDimensiones(p: Params, s: Dimensiones): Params {
  const out: Params = {}
  const nuevos: Dimensiones = { d: s.d, bf: s.bf, tw: s.tw, tf: s.tf }
  for (const k of ['d', 'bf', 'tw', 'tf'] as const) {
    if (p[k] !== nuevos[k]) out[k] = nuevos[k]
  }
  return out
}

function enTabla(tabla: Tabla, clave: ParamValor | undefined): Dimensiones | undefined {
  return typeof clave === 'string' && Object.hasOwn(tabla, clave) ? tabla[clave] : undefined
}

/** placa_base.autollenar: solo reacciona a "perfil"; "Manual" no altera nada. */
function autollenarPlacaBase(p: Params, campo: string): Params {
  if (campo !== 'perfil') return {}
  const s = enTabla(W_DB, p.perfil)
  return s ? cambiosDimensiones(p, s) : {}
}

/** profile.autollenar: reacciona a cualquier campo, según la serie comercial. */
function autollenarPerfil(p: Params): Params {
  const s = enTabla(W_DB, p.serie) ?? enTabla(HE_DB, p.serie)
  return s ? cambiosDimensiones(p, s) : {}
}

/** anchor_bolt.autollenar: con PG y "1 in", fuerza d_perno a "25.4". */
function autollenarPerno(p: Params, _campo: string): Params {
  const pg = String(p.tipo ?? '').startsWith('PG')
  const inch = pg && p.d_nominal === '1 in'
  if (inch && String(p.d_perno ?? '') !== '25.4') return { d_perno: '25.4' }
  return {}
}

const AUTOLLENADO: Record<string, Autollenado> = {
  placa_base: autollenarPlacaBase,
  perfil: autollenarPerfil,
  perno_anclaje: autollenarPerno,
}

/** Bloque "Referencia 20" de PedestalPanel.on_change: solo en la TRANSICIÓN al modo. */
function referenciaPedestal(p: Params, campo: string, previo: Params | undefined): Params {
  if (campo !== 'preset' || previo === undefined) return {}
  if (presetEfectivo(p.preset) !== PRESET_REF20) return {}
  if (presetEfectivo(previo.preset ?? PRESET_DEFAULT) === PRESET_REF20) return {}
  const out: Params = {}
  for (const [k, v] of Object.entries(REF20_VALORES)) {
    if (!igual(p[k], v)) out[k] = v
  }
  return out
}

/** Claves que el Panel original cambia cuando el usuario modifica `campo`. */
export function autollenarUi(moduloId: string, p: Params, campo: string, previo?: Params): Params {
  exigirModulo(moduloId)
  const out: Params = {}
  if (Object.hasOwn(AUTOLLENADO, moduloId)) {
    Object.assign(out, AUTOLLENADO[moduloId](p, campo))
  }
  if (moduloId === 'pedestal') Object.assign(out, referenciaPedestal(p, campo, previo))
  return out
}

/** Nuevo Params completo tras asignar `campo`, aplicar autollenado y recalcular _escala. */
export function aplicarCambio(
  moduloId: string,
  p: Params,
  campo: string,
  valor: ParamValor,
  previo?: Params,
): Params {
  const nuevo: Params = { ...p, [campo]: valor }
  const final: Params = { ...nuevo, ...autollenarUi(moduloId, nuevo, campo, previo) }
  final._escala = factorEscala(String(final.escala ?? ''))
  return final
}
