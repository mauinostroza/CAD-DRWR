// Página principal de CAD-DRWR: módulos y parámetros, visor del dibujo, herramientas y estado.
import { useCallback, useEffect, useId, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { saveBlob } from '../lib_client'
import EnvioCadDialog from './EnvioCadDialog'
import { ESCALAS } from './catalogos'
import { descargarDxf, descargarLote, listarModulos } from './api'
import { Formulario } from './Formulario'
import SapFundacionPanel from './SapFundacionPanel'
import {
  MAX_GEOM_BYTES,
  MAX_PLANTILLAS,
  aJsonSeguro,
  importarPlantillaEscritorio,
  migrarEstado,
  type EstadoCadDrwr,
  type Plantilla,
} from './estado'
import { useDibujo } from './useDibujo'
import { useHistorial } from './useHistorial'
import type { Lamina, ModuloInfo, Params } from './tipos'
import { colorCapa } from './vista/capas'
import { aPngBlob, aSvg } from './vista/exportar'
import type { Medida } from './vista/geometria'
import { VistaSvg } from './vista/VistaSvg'
import './cad_drwr.css'

export type CadDrwrPageProps = {
  state: unknown
  onState: (v: unknown) => void
  /** Otras props del contenedor (p. ej. onReport) se ignoran. */
  [otras: string]: unknown
}

/** Lo que el usuario edita y que deshace/rehace el historial. */
type Edicion = {
  modulo: string
  params: Record<string, Params>
  lamina: Lamina
  geom?: unknown
}

type Panel = 'capas' | 'exportar' | 'plantillas' | 'solapes' | null
type Aviso = { tipo: 'ok' | 'error'; texto: string }
type Cursor = { x: number; y: number }

const GUARDADO_MS = 300
const LADO_PNG_PX = 2400
const INTENTOS_MODULOS = 3
const ESPERA_REINTENTO_MS = 250
const ARCHIVO_LOTE = 'cad_drwr_lote.zip'
const FORMATO = new Intl.NumberFormat('es', { maximumFractionDigits: 1 })

// ------------------------------------------------------------ carga de módulos --
// Caché a nivel de módulo: la lista se pide una sola vez y se reintenta si falla.
let cargaModulos: Promise<ModuloInfo[]> | null = null

const esperar = (ms: number) => new Promise<void>((resolver) => setTimeout(resolver, ms))

async function pedirModulosConReintento(): Promise<ModuloInfo[]> {
  let ultimo: unknown
  for (let i = 0; i < INTENTOS_MODULOS; i++) {
    try {
      return await listarModulos()
    } catch (e) {
      ultimo = e
      if (i < INTENTOS_MODULOS - 1) await esperar(ESPERA_REINTENTO_MS * 2 ** i)
    }
  }
  throw ultimo
}

function cargarModulos(): Promise<ModuloInfo[]> {
  if (cargaModulos === null) {
    cargaModulos = pedirModulosConReintento().catch((e: unknown) => {
      cargaModulos = null
      throw e
    })
  }
  return cargaModulos
}

/** Olvida la lista cacheada para volver a pedirla (usado al reintentar y en las pruebas). */
export function reiniciarCargaModulos(): void {
  cargaModulos = null
}

function mensajeError(e: unknown): string {
  return e instanceof Error ? e.message : 'Error desconocido'
}

function useModulos() {
  const [estado, setEstado] = useState<{ modulos: ModuloInfo[] | null; error: string | null }>({
    modulos: null,
    error: null,
  })
  const [intento, setIntento] = useState(0)

  useEffect(() => {
    let vivo = true
    cargarModulos().then(
      (modulos) => {
        if (vivo) setEstado({ modulos, error: null })
      },
      (e: unknown) => {
        if (vivo) setEstado({ modulos: null, error: mensajeError(e) })
      },
    )
    return () => {
      vivo = false
    }
  }, [intento])

  const reintentar = useCallback(() => {
    reiniciarCargaModulos()
    setEstado({ modulos: null, error: null })
    setIntento((n) => n + 1)
  }, [])

  return { ...estado, reintentar }
}

// ------------------------------------------------------------------ utilidades --
function valoresDe(modulo: ModuloInfo, params: Record<string, Params>): Params {
  return { ...modulo.defaults, ...(params[modulo.id] ?? {}) }
}

/** Quita las claves derivadas que no forman parte de la plantilla del escritorio. */
function sinDerivadas(p: Params): Params {
  const { _escala: _e, _geom: _g, ...resto } = p
  return resto
}

/** La geometría viaja en `_geom` dentro de params (contrato del servidor, no es un ParamValor). */
function conGeom(valores: Params, geom: unknown): Params {
  if (geom === undefined || geom === null) return valores
  return { ...valores, _geom: geom } as unknown as Params
}

function leerTexto(archivo: Blob): Promise<string> {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader()
    lector.onload = () => resolver(String(lector.result))
    lector.onerror = () => rechazar(lector.error ?? new Error('No se pudo leer el archivo'))
    lector.readAsText(archivo)
  })
}

const crearId = (): string => Date.now().toString(36) + Math.random().toString(36).slice(2, 8)

function nombreSeguro(nombre: string): string {
  return nombre.trim().replace(/[\\/:*?"<>|]+/g, '_') || 'plantilla'
}

// ------------------------------------------------------------- subcomponentes --
/** Espesor por defecto del módulo interactivo: el borrador de texto permite escribir libremente. */
function CampoEspesor({
  id,
  valor,
  onElegir,
}: {
  id: string
  valor: number
  onElegir: (n: number) => void
}) {
  const [texto, setTexto] = useState(String(valor))
  useEffect(() => {
    setTexto((t) => (Number(t) === valor ? t : String(valor)))
  }, [valor])

  return (
    <>
      <label htmlFor={id}>Espesor por defecto (mm)</label>
      <input
        id={id}
        type="number"
        min={0}
        step={1}
        value={texto}
        onChange={(e) => {
          const t = e.target.value
          setTexto(t)
          const n = Number(t)
          if (t.trim() !== '' && Number.isFinite(n) && n >= 0) onElegir(n)
        }}
      />
    </>
  )
}

// ------------------------------------------------------------------- página --
export default function CadDrwrPage({ state, onState }: CadDrwrPageProps) {
  const prefijo = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const [inicial] = useState(() => migrarEstado(state))
  const historial = useHistorial<Edicion>({
    modulo: inicial.modulo,
    params: inicial.params,
    lamina: inicial.lamina,
    geom: inicial.geom,
  })
  const { valor: edicion, fijar, deshacer, rehacer, puedeDeshacer, puedeRehacer } = historial

  const [plantillas, setPlantillas] = useState<Plantilla[]>(inicial.plantillas)
  const [capasOcultas, setCapasOcultas] = useState<string[]>(inicial.capasOcultas)
  const { modulos, error: errorModulos, reintentar } = useModulos()

  const [panelAbierto, setPanelAbierto] = useState(true)
  const [panel, setPanel] = useState<Panel>(null)
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [medir, setMedir] = useState(false)
  const [medida, setMedida] = useState<Medida | null>(null)
  const [cursor, setCursor] = useState<Cursor | null>(null)
  const [ajuste, setAjuste] = useState(0)
  const [exportando, setExportando] = useState(false)
  const [envioAbierto, setEnvioAbierto] = useState(false)
  const [dialogoLamina, setDialogoLamina] = useState(false)
  const [nombrePlantilla, setNombrePlantilla] = useState('')

  const modulo: ModuloInfo | undefined =
    modulos?.find((m) => m.id === edicion.modulo) ?? modulos?.[0]
  const interactivo = modulo?.interactivo === true
  const valores = useMemo<Params>(
    () => (modulo ? valoresDe(modulo, edicion.params) : {}),
    [modulo, edicion.params],
  )
  const pedido = useMemo<Params>(
    () => (interactivo ? conGeom(valores, edicion.geom) : valores),
    [interactivo, valores, edicion.geom],
  )
  const { dibujo, cargando, error, tiempoMs } = useDibujo(
    modulo?.id ?? '',
    pedido,
    edicion.lamina,
    interactivo,
  )

  // Al llegar el dibujo de OTRO módulo se reajusta la vista; al editar el mismo se conserva.
  const moduloDibujado = dibujo?.modulo
  useEffect(() => setAjuste((n) => n + 1), [moduloDibujado])

  const capasPresentes = useMemo(
    () => [...new Set(dibujo?.render.map((e) => e.l) ?? [])].sort(),
    [dibujo],
  )
  const solapes = dibujo?.solapes ?? []

  // ----------------------------------------------------------- persistencia --
  const persistido = useMemo<EstadoCadDrwr>(
    () => ({
      schema_version: 1,
      modulo: edicion.modulo,
      params: edicion.params,
      lamina: edicion.lamina,
      plantillas,
      capasOcultas,
      geom: edicion.geom,
    }),
    [edicion, plantillas, capasOcultas],
  )

  const onStateRef = useRef(onState)
  useEffect(() => {
    onStateRef.current = onState
  })

  // Guardado con debounce. Un cambio pendiente se envía al desmontar, para no perderlo.
  const sinGuardar = useRef<{ valor: unknown } | null>(null)
  useEffect(() => {
    sinGuardar.current = { valor: aJsonSeguro(persistido) }
    const espera = setTimeout(() => {
      const pendiente = sinGuardar.current
      sinGuardar.current = null
      if (pendiente) onStateRef.current(pendiente.valor)
    }, GUARDADO_MS)
    return () => clearTimeout(espera)
  }, [persistido])

  useEffect(
    () => () => {
      const pendiente = sinGuardar.current
      if (pendiente) {
        sinGuardar.current = null
        onStateRef.current(pendiente.valor)
      }
    },
    [],
  )

  // ------------------------------------------------------------- atajos --
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent): void => {
      if (!(e.ctrlKey || e.metaKey)) return
      const t = e.target as HTMLElement | null
      // En campos de texto se respeta el deshacer nativo del navegador.
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      const tecla = e.key.toLowerCase()
      if (tecla === 'z' && !e.shiftKey) {
        e.preventDefault()
        deshacer()
      } else if (tecla === 'y' || (tecla === 'z' && e.shiftKey)) {
        e.preventDefault()
        rehacer()
      }
    }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [deshacer, rehacer])

  // ------------------------------------------------------------ acciones --
  const cambiarParams = (id: string, nuevos: Params, origen?: string) =>
    fijar({ ...edicion, params: { ...edicion.params, [id]: nuevos } }, origen)

  const cambiarLamina = (cambios: Partial<Lamina>, origen: string) =>
    fijar({ ...edicion, lamina: { ...edicion.lamina, ...cambios } }, origen)

  const togglePanel = (p: Exclude<Panel, null>) => setPanel((actual) => (actual === p ? null : p))

  const alternarCapa = (capa: string) =>
    setCapasOcultas((previas) =>
      previas.includes(capa) ? previas.filter((c) => c !== capa) : [...previas, capa],
    )

  const exportar = async (formato: 'svg' | 'png' | 'dxf' | 'lote'): Promise<void> => {
    setPanel(null)
    setAviso(null)
    setExportando(true)
    try {
      if (formato === 'lote') {
        const items = (modulos ?? [])
          .filter((m) => !m.interactivo)
          .map((m) => ({ modulo: m.id, params: valoresDe(m, edicion.params) }))
        saveBlob(await descargarLote(items, edicion.lamina), ARCHIVO_LOTE)
      } else if (!dibujo || !modulo) {
        throw new Error('No hay dibujo que exportar.')
      } else if (formato === 'dxf') {
        saveBlob(await descargarDxf(modulo.id, pedido, edicion.lamina), `${modulo.id}.dxf`)
      } else {
        const svg = aSvg(dibujo, { capasOcultas, fondo: 'claro' })
        if (formato === 'svg') {
          saveBlob(new Blob([svg], { type: 'image/svg+xml' }), `${modulo.id}.svg`)
        } else {
          saveBlob(await aPngBlob(svg, LADO_PNG_PX), `${modulo.id}.png`)
        }
      }
    } catch (e) {
      setAviso({ tipo: 'error', texto: `No se pudo exportar: ${mensajeError(e)}` })
    } finally {
      setExportando(false)
    }
  }

  const guardarPlantilla = () => {
    const nombre = nombrePlantilla.trim()
    if (!modulo) return
    if (nombre === '') {
      setAviso({ tipo: 'error', texto: 'Escriba un nombre para la plantilla.' })
      return
    }
    if (plantillas.length >= MAX_PLANTILLAS) {
      setAviso({
        tipo: 'error',
        texto: `Ya hay ${MAX_PLANTILLAS} plantillas. Borre alguna antes de guardar otra.`,
      })
      return
    }
    setPlantillas((ps) => [
      ...ps,
      { id: crearId(), nombre, modulo: modulo.id, params: sinDerivadas(valores) },
    ])
    setNombrePlantilla('')
    setAviso({ tipo: 'ok', texto: `Plantilla «${nombre}» guardada.` })
  }

  const aplicarPlantilla = (p: Plantilla) => {
    if (!modulos?.some((m) => m.id === p.modulo)) {
      setAviso({
        tipo: 'error',
        texto: `La plantilla «${p.nombre}» es del módulo «${p.modulo}», que no existe en el servidor.`,
      })
      return
    }
    fijar({ ...edicion, modulo: p.modulo, params: { ...edicion.params, [p.modulo]: p.params } })
    setAviso({ tipo: 'ok', texto: `Plantilla «${p.nombre}» aplicada.` })
  }

  const exportarPlantilla = (p: Plantilla) => {
    const blob = new Blob([JSON.stringify(p.params, null, 2)], { type: 'application/json' })
    saveBlob(blob, `${nombreSeguro(p.nombre)}.json`)
  }

  const importarArchivo = async (archivo: File): Promise<void> => {
    if (!modulo) return
    setAviso(null)
    let raw: unknown
    try {
      raw = JSON.parse(await leerTexto(archivo))
    } catch {
      setAviso({ tipo: 'error', texto: 'El archivo no es JSON válido.' })
      return
    }
    const imp = importarPlantillaEscritorio(raw)
    const conocidas = imp
      ? Object.keys(imp.params).filter(
          (k) => Object.hasOwn(modulo.defaults, k) || modulo.campos.some((c) => c.key === k),
        )
      : []
    if (!imp || (conocidas.length === 0 && imp.geom === undefined)) {
      setAviso({
        tipo: 'error',
        texto: `La plantilla no se reconoce para el módulo «${modulo.nombre}».`,
      })
      return
    }
    if (imp.geom !== undefined && JSON.stringify(imp.geom).length > MAX_GEOM_BYTES) {
      setAviso({
        tipo: 'error',
        texto: 'La geometría de la plantilla es demasiado grande para guardarse (límite 500 KB).',
      })
      return
    }
    const nuevosParams = Object.fromEntries(conocidas.map((k) => [k, imp.params[k]]))
    const claves = Object.keys(raw as Record<string, unknown>)
    const trajoLamina = claves.includes('_sheet_enabled') || claves.includes('_sheet_metadata')
    const lamina: Lamina = trajoLamina
      ? {
          activa: imp.lamina?.activa === true,
          proyecto: imp.lamina?.proyecto ?? '',
          numero_plano: imp.lamina?.numero_plano ?? '',
          revision: imp.lamina?.revision ?? '',
        }
      : edicion.lamina
    fijar({
      ...edicion,
      lamina,
      geom: imp.geom !== undefined ? imp.geom : edicion.geom,
      params: { ...edicion.params, [modulo.id]: { ...valores, ...nuevosParams } },
    })
    setAviso({
      tipo: 'ok',
      texto:
        conocidas.length > 0 ? 'Plantilla importada.' : 'Se importó la geometría de la plantilla.',
    })
  }

  const alElegirArchivo = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0]
    e.target.value = ''
    if (archivo) {
      importarArchivo(archivo).catch((err: unknown) =>
        setAviso({ tipo: 'error', texto: `No se pudo leer la plantilla: ${mensajeError(err)}` }),
      )
    }
  }

  // ----------------------------------------------------------------- vista --
  const mensajeVacio =
    interactivo && edicion.geom === undefined
      ? 'Lea la geometría desde SAP2000 en el panel izquierdo para ver el dibujo.'
      : cargando
        ? 'Calculando el dibujo…'
        : 'Sin dibujo que mostrar.'

  const alternarLamina = () => cambiarLamina({ activa: !edicion.lamina.activa }, 'lamina:activa')

  return (
    <div className="cad-pagina" aria-busy={cargando || exportando || undefined}>
      <aside
        className={'cad-columna cad-columna--izq' + (panelAbierto ? '' : ' cad-columna--plegada')}
        aria-label="Módulos y parámetros"
      >
        <button
          type="button"
          className="cad-plegar"
          aria-expanded={panelAbierto}
          aria-controls={`${prefijo}-izq`}
          onClick={() => setPanelAbierto((v) => !v)}
        >
          {panelAbierto ? 'Ocultar módulos y parámetros' : 'Mostrar módulos y parámetros'}
        </button>
        <div id={`${prefijo}-izq`} className="cad-columna__cuerpo">
          {modulos === null && errorModulos === null && (
            <p className="cad-aviso" role="status">
              Cargando módulos…
            </p>
          )}
          {errorModulos !== null && (
            <div className="cad-error" role="alert">
              <p>No se pudieron cargar los módulos: {errorModulos}</p>
              <p>Compruebe la conexión con el servidor e inténtelo de nuevo.</p>
              <button type="button" onClick={reintentar}>
                Reintentar
              </button>
            </div>
          )}
          {modulos !== null && modulo && (
            <>
              <nav aria-label="Módulos" className="cad-modulos">
                {modulos.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className="cad-modulo"
                    aria-current={m.id === modulo.id ? 'true' : undefined}
                    onClick={() => fijar({ ...edicion, modulo: m.id })}
                  >
                    {m.nombre}
                  </button>
                ))}
              </nav>
              {interactivo ? (
                <>
                  <SapFundacionPanel
                    onGeom={(g) => fijar({ ...edicion, geom: g }, 'geom')}
                    geomActual={edicion.geom}
                  />
                  <div
                    className="cad-formulario"
                    role="group"
                    aria-label={`Parámetros de ${modulo.nombre}`}
                  >
                    <label htmlFor={`${prefijo}-escala`}>Escala de acotado</label>
                    <select
                      id={`${prefijo}-escala`}
                      value={String(valores.escala ?? '1:50')}
                      onChange={(e) =>
                        cambiarParams(
                          modulo.id,
                          { ...valores, escala: e.target.value },
                          `p:${modulo.id}`,
                        )
                      }
                    >
                      {ESCALAS.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                    <CampoEspesor
                      id={`${prefijo}-espesor`}
                      valor={Number(valores.espesor_default ?? 0)}
                      onElegir={(n) =>
                        cambiarParams(
                          modulo.id,
                          { ...valores, espesor_default: n },
                          `p:${modulo.id}`,
                        )
                      }
                    />
                  </div>
                </>
              ) : (
                <Formulario
                  modulo={modulo}
                  valores={valores}
                  onCambio={(nuevos) => cambiarParams(modulo.id, nuevos, `p:${modulo.id}`)}
                />
              )}
            </>
          )}
        </div>
      </aside>

      <section className="cad-centro" aria-label="Dibujo">
        <div className="cad-barra-envoltura">
          <div className="cad-barra" role="group" aria-label="Herramientas del dibujo">
            <button
              type="button"
              onClick={() => setAjuste((n) => n + 1)}
              title="Ajustar el dibujo a la ventana"
            >
              Ajustar
            </button>
            <button
              type="button"
              aria-pressed={medir}
              onClick={() => setMedir((v) => !v)}
              title="Medir distancias con dos clics (Esc cancela el punto en curso)"
            >
              Medir
            </button>
            <button
              type="button"
              aria-expanded={panel === 'capas'}
              aria-controls={`${prefijo}-panel`}
              disabled={!dibujo}
              onClick={() => togglePanel('capas')}
              title="Mostrar u ocultar capas"
            >
              Capas
            </button>
            <button
              type="button"
              aria-pressed={edicion.lamina.activa}
              onClick={alternarLamina}
              title="Dibujar la lámina con cajetín"
            >
              Lámina
            </button>
            <button
              type="button"
              onClick={() => setDialogoLamina(true)}
              title="Editar proyecto, número de plano y revisión"
            >
              Datos de lámina
            </button>
            <button
              type="button"
              aria-expanded={panel === 'exportar'}
              aria-controls={`${prefijo}-panel`}
              onClick={() => togglePanel('exportar')}
              disabled={exportando}
            >
              Exportar
            </button>
            <button
              type="button"
              aria-expanded={panel === 'plantillas'}
              aria-controls={`${prefijo}-panel`}
              onClick={() => togglePanel('plantillas')}
            >
              Plantillas
            </button>
            <button
              type="button"
              aria-expanded={panel === 'solapes'}
              aria-controls={`${prefijo}-panel`}
              disabled={!dibujo}
              onClick={() => togglePanel('solapes')}
            >
              {solapes.length > 0
                ? `Revisar anotaciones (${solapes.length})`
                : 'Revisar anotaciones'}
            </button>
            <button
              type="button"
              aria-label="Deshacer"
              title="Deshacer (Ctrl+Z)"
              disabled={!puedeDeshacer}
              onClick={deshacer}
            >
              Deshacer
            </button>
            <button
              type="button"
              aria-label="Rehacer"
              title="Rehacer (Ctrl+Y)"
              disabled={!puedeRehacer}
              onClick={rehacer}
            >
              Rehacer
            </button>
            <button
              type="button"
              disabled={!dibujo}
              onClick={() => setEnvioAbierto(true)}
              title="Enviar el dibujo al CAD"
            >
              Enviar a CAD
            </button>
          </div>

          {panel !== null && (
            <div id={`${prefijo}-panel`} className="cad-panel">
              {panel === 'capas' && (
                <section aria-label="Capas">
                  {capasPresentes.length === 0 && (
                    <p className="cad-nota">El dibujo no tiene capas.</p>
                  )}
                  {capasPresentes.map((capa) => (
                    <label key={capa} className="cad-fila-capa">
                      <input
                        type="checkbox"
                        checked={!capasOcultas.includes(capa)}
                        onChange={() => alternarCapa(capa)}
                      />
                      <span
                        className="cad-chip"
                        aria-hidden="true"
                        style={{ background: colorCapa(capa, 'oscuro') }}
                      />
                      {capa}
                    </label>
                  ))}
                </section>
              )}

              {panel === 'exportar' && (
                <section aria-label="Exportar" className="cad-lista-botones">
                  <button
                    type="button"
                    disabled={!dibujo || exportando}
                    onClick={() => exportar('svg')}
                  >
                    SVG
                  </button>
                  <button
                    type="button"
                    disabled={!dibujo || exportando}
                    onClick={() => exportar('png')}
                  >
                    PNG
                  </button>
                  <button
                    type="button"
                    disabled={!dibujo || exportando}
                    onClick={() => exportar('dxf')}
                  >
                    DXF
                  </button>
                  <button
                    type="button"
                    disabled={exportando || !modulos}
                    onClick={() => exportar('lote')}
                  >
                    Todos los módulos (ZIP de DXF)
                  </button>
                  <p className="cad-nota">
                    El ZIP omite Fundación SAP2000, que necesita su geometría.
                  </p>
                </section>
              )}

              {panel === 'plantillas' && (
                <section aria-label="Plantillas" className="cad-plantillas">
                  <div className="cad-fila-campo">
                    <label htmlFor={`${prefijo}-nombre-pl`}>Nombre de la plantilla</label>
                    <input
                      id={`${prefijo}-nombre-pl`}
                      type="text"
                      value={nombrePlantilla}
                      onChange={(e) => setNombrePlantilla(e.target.value)}
                    />
                  </div>
                  <div className="cad-lista-botones">
                    <button type="button" disabled={!modulo} onClick={guardarPlantilla}>
                      Guardar actual
                    </button>
                    <label className="cad-boton">
                      Importar JSON del escritorio
                      <input
                        type="file"
                        accept=".json,application/json"
                        className="cad-oculto"
                        onChange={alElegirArchivo}
                      />
                    </label>
                  </div>
                  {plantillas.length === 0 ? (
                    <p className="cad-nota">No hay plantillas guardadas.</p>
                  ) : (
                    <ul className="cad-lista">
                      {plantillas.map((p) => (
                        <li key={p.id}>
                          <span>
                            {p.nombre} <small>({p.modulo})</small>
                          </span>
                          <button
                            type="button"
                            aria-label={`Aplicar plantilla ${p.nombre}`}
                            onClick={() => aplicarPlantilla(p)}
                          >
                            Aplicar
                          </button>
                          <button
                            type="button"
                            aria-label={`Exportar plantilla ${p.nombre} como JSON`}
                            onClick={() => exportarPlantilla(p)}
                          >
                            Exportar JSON
                          </button>
                          <button
                            type="button"
                            aria-label={`Borrar plantilla ${p.nombre}`}
                            onClick={() => setPlantillas((ps) => ps.filter((x) => x.id !== p.id))}
                          >
                            Borrar
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              )}

              {panel === 'solapes' && (
                <section aria-label="Anotaciones solapadas">
                  {solapes.length === 0 ? (
                    <p className="cad-nota">No hay solapes de anotaciones.</p>
                  ) : (
                    <ol>
                      {solapes.map((grupo, i) => (
                        <li key={i}>{grupo.join(' · ')}</li>
                      ))}
                    </ol>
                  )}
                </section>
              )}
            </div>
          )}
        </div>

        {aviso !== null && (
          <p
            className={aviso.tipo === 'error' ? 'cad-error' : 'cad-aviso'}
            role={aviso.tipo === 'error' ? 'alert' : 'status'}
          >
            {aviso.texto}{' '}
            <button type="button" aria-label="Cerrar aviso" onClick={() => setAviso(null)}>
              Cerrar
            </button>
          </p>
        )}

        {error !== null && (
          <p className="cad-error" role="alert">
            No se pudo actualizar el dibujo: {error}
            {dibujo ? '. Se muestra el último dibujo correcto.' : ''}
          </p>
        )}

        <div className="cad-lienzo">
          {dibujo ? (
            <VistaSvg
              dibujo={dibujo}
              capasOcultas={capasOcultas}
              ajusteToken={ajuste}
              modoMedir={medir}
              onMedida={setMedida}
              onCursor={setCursor}
            />
          ) : (
            <p className="cad-vacio">{mensajeVacio}</p>
          )}
        </div>

        <footer className="cad-pie" aria-label="Estado del dibujo">
          <span>Entidades: {dibujo ? dibujo.n_render : '—'}</span>
          <span>Tiempo: {tiempoMs !== null ? `${tiempoMs} ms` : '—'}</span>
          <span>
            Cursor: X {cursor ? FORMATO.format(cursor.x) : '—'} mm · Y{' '}
            {cursor ? FORMATO.format(cursor.y) : '—'} mm
          </span>
          <span>
            Medida:{' '}
            {medida
              ? `Δx ${FORMATO.format(medida.dx)} · Δy ${FORMATO.format(medida.dy)} · dist. ${FORMATO.format(medida.dist)} mm · ángulo ${FORMATO.format(medida.anguloDeg)}°`
              : '—'}
          </span>
          <span>{solapes.length > 0 ? `Solapes: ${solapes.length}` : 'Sin solapes'}</span>
          {cargando && <span role="status">Calculando…</span>}
        </footer>
      </section>

      {dialogoLamina && (
        <div
          className="cad-velo"
          onKeyDown={(e) => {
            if (e.key === 'Escape') setDialogoLamina(false)
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={`${prefijo}-titulo-lamina`}
            className="cad-dialogo"
          >
            <h2 id={`${prefijo}-titulo-lamina`}>Datos de lámina</h2>
            <div className="cad-fila-campo">
              <label htmlFor={`${prefijo}-proyecto`}>Proyecto</label>
              <input
                id={`${prefijo}-proyecto`}
                type="text"
                value={edicion.lamina.proyecto}
                onChange={(e) => cambiarLamina({ proyecto: e.target.value }, 'lamina:proyecto')}
              />
            </div>
            <div className="cad-fila-campo">
              <label htmlFor={`${prefijo}-plano`}>Número de plano</label>
              <input
                id={`${prefijo}-plano`}
                type="text"
                value={edicion.lamina.numero_plano}
                onChange={(e) =>
                  cambiarLamina({ numero_plano: e.target.value }, 'lamina:numero_plano')
                }
              />
            </div>
            <div className="cad-fila-campo">
              <label htmlFor={`${prefijo}-revision`}>Revisión</label>
              <input
                id={`${prefijo}-revision`}
                type="text"
                value={edicion.lamina.revision}
                onChange={(e) => cambiarLamina({ revision: e.target.value }, 'lamina:revision')}
              />
            </div>
            <div className="cad-lista-botones">
              <button type="button" onClick={() => setDialogoLamina(false)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {envioAbierto && (
        <EnvioCadDialog
          dibujo={dibujo}
          nombre={modulo?.id ?? ''}
          onCerrar={() => setEnvioAbierto(false)}
        />
      )}
    </div>
  )
}
