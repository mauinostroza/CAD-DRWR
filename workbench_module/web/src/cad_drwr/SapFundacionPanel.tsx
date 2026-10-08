import { useEffect, useRef, useState } from 'react'
import {
  MENSAJE_SIN_EMPAREJAR,
  cancelarFundacion,
  estadoFundacion,
  gruposSap,
  iniciarFundacion,
  obtenerCredenciales,
  type BridgeCreds,
  type EstadoFundacion,
  type GrupoSap,
} from './bridgeCad'
import {
  esGeomValida,
  incluirZapata,
  quitarPedestal,
  resumenGeom,
  setEspesorZapata,
  setPedestal,
  type FundacionGeom,
  type PedestalGeom,
} from './fundacion'
import './sap_fundacion.css'

type Props = {
  onGeom: (geom: unknown) => void
  geomActual?: unknown
}

type Trabajo = {
  grupo: string
  job: string | null
  estado: EstadoFundacion | null
  cancelando: boolean
}

const INTERVALO_SONDEO_MS = 1000

function mensajeDe(e: unknown): string {
  return e instanceof Error ? e.message : 'Error desconocido.'
}

function avisoDe(p: PedestalGeom): string {
  if (p.motivo_aviso) return p.motivo_aviso
  return p.aproximado ? 'Dimensión aproximada' : ''
}

/** Campo numérico con borrador local: permite escribir "1." sin perder el punto decimal. */
function CampoNumero({
  etiqueta,
  valor,
  onCambio,
}: {
  etiqueta: string
  valor: number | null
  onCambio: (v: number) => void
}) {
  const textoDe = (v: number | null) => (v === null ? '' : String(v))
  const [borrador, setBorrador] = useState(textoDe(valor))

  useEffect(() => {
    setBorrador((prev) => (prev.trim() !== '' && Number(prev) === valor ? prev : textoDe(valor)))
  }, [valor])

  return (
    <input
      type="number"
      aria-label={etiqueta}
      min="0"
      step="any"
      value={borrador}
      onChange={(e) => {
        const t = e.target.value
        setBorrador(t)
        const n = Number(t)
        if (t.trim() !== '' && Number.isFinite(n) && n > 0) onCambio(n)
      }}
      onBlur={() => setBorrador(textoDe(valor))}
    />
  )
}

export default function SapFundacionPanel({ onGeom, geomActual }: Props) {
  const [grupos, setGrupos] = useState<GrupoSap[] | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [trabajo, setTrabajo] = useState<Trabajo | null>(null)
  // Geometría completa (incluye zapatas excluidas) e índices de las incluidas.
  const [completa, setCompleta] = useState<FundacionGeom | null>(null)
  const [incluidas, setIncluidas] = useState<number[] | null>(null)

  const vivoRef = useRef(true)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const jobRef = useRef<{ creds: BridgeCreds; job: string } | null>(null)
  const onGeomRef = useRef(onGeom)
  onGeomRef.current = onGeom

  useEffect(() => {
    vivoRef.current = true
    return () => {
      vivoRef.current = false
      if (timerRef.current !== null) clearTimeout(timerRef.current)
    }
  }, [])

  async function credencialesOAviso(): Promise<BridgeCreds | null> {
    const c = await obtenerCredenciales()
    if (c.source === 'none') {
      setMensaje(MENSAJE_SIN_EMPAREJAR)
      return null
    }
    return c
  }

  async function leerGrupos() {
    setMensaje(null)
    try {
      const c = await credencialesOAviso()
      if (!c) return
      const r = await gruposSap(c)
      if (vivoRef.current) setGrupos(r.grupos.filter((g) => g.n_shells > 0))
    } catch (e) {
      if (vivoRef.current) setMensaje(mensajeDe(e))
    }
  }

  function aceptarGeom(g: FundacionGeom) {
    setCompleta(g)
    setIncluidas(g.zapatas.map((_, i) => i))
    onGeomRef.current(g)
  }

  function programarSondeo(c: BridgeCreds, job: string) {
    timerRef.current = setTimeout(() => void sondear(c, job), INTERVALO_SONDEO_MS)
  }

  async function sondear(c: BridgeCreds, job: string) {
    timerRef.current = null
    try {
      const st = await estadoFundacion(c, job)
      if (!vivoRef.current || jobRef.current?.job !== job) return
      if (st.estado === 'en_curso') {
        setTrabajo((t) => (t && t.job === job ? { ...t, estado: st } : t))
        programarSondeo(c, job)
        return
      }
      jobRef.current = null
      setTrabajo(null)
      if (st.estado === 'listo') {
        if (esGeomValida(st.resultado)) {
          setMensaje(null)
          aceptarGeom(st.resultado)
        } else {
          setMensaje('El puente devolvió una geometría no reconocida. Actualice SAP2000Bridge.')
        }
      } else if (st.estado === 'error') {
        setMensaje(`No se pudo leer la fundación: ${st.error ?? 'error sin detalle.'}`)
      } else {
        setMensaje('Lectura cancelada.')
      }
    } catch (e) {
      if (!vivoRef.current || jobRef.current?.job !== job) return
      jobRef.current = null
      setTrabajo(null)
      setMensaje(mensajeDe(e))
    }
  }

  async function leerFundacion(grupo: string) {
    if (jobRef.current || trabajo) return
    setMensaje(null)
    setTrabajo({ grupo, job: null, estado: null, cancelando: false })
    try {
      const c = await credencialesOAviso()
      if (!c) {
        setTrabajo(null)
        return
      }
      const { job } = await iniciarFundacion(c, grupo)
      if (!vivoRef.current) return
      jobRef.current = { creds: c, job }
      setTrabajo({ grupo, job, estado: null, cancelando: false })
      programarSondeo(c, job)
    } catch (e) {
      if (!vivoRef.current) return
      setTrabajo(null)
      setMensaje(mensajeDe(e))
    }
  }

  async function cancelar() {
    const j = jobRef.current
    if (!j) return
    setTrabajo((t) => (t ? { ...t, cancelando: true } : t))
    try {
      await cancelarFundacion(j.creds, j.job)
    } catch (e) {
      if (!vivoRef.current) return
      setMensaje(mensajeDe(e))
      setTrabajo((t) => (t ? { ...t, cancelando: false } : t))
    }
  }

  // Base de edición: la lectura más reciente o, si no la hay, la geometría recibida.
  const base: FundacionGeom | null = completa ?? (esGeomValida(geomActual) ? geomActual : null)
  const incl: number[] = base ? (incluidas ?? base.zapatas.map((_, i) => i)) : []

  /** Aplica un cambio sobre la geometría completa y emite la versión con las zapatas incluidas. */
  function aplicar(fn: (g: FundacionGeom) => FundacionGeom, nuevasIncluidas?: number[]) {
    if (!base) return
    const nueva = fn(base)
    const inclusion = nuevasIncluidas ?? incl
    setCompleta(nueva)
    setIncluidas(inclusion)
    onGeomRef.current(incluirZapata(nueva, inclusion))
  }

  function alternarIncluir(i: number) {
    const nuevas = incl.includes(i)
      ? incl.filter((k) => k !== i)
      : [...incl, i].sort((a, b) => a - b)
    aplicar((g) => g, nuevas)
  }

  const hechas = trabajo?.estado?.hechas ?? 0
  const total = trabajo?.estado?.total ?? 0
  const pct = total > 0 ? Math.min(100, Math.round((hechas / total) * 100)) : 0
  const resumen = base ? resumenGeom(base) : null

  return (
    <div className="sap-fund">
      <section className="sap-fund-grupos" aria-label="Grupos de SAP2000">
        <button type="button" onClick={() => void leerGrupos()} disabled={trabajo !== null}>
          Leer grupos
        </button>
        {grupos !== null && grupos.length === 0 && (
          <p>No hay grupos con shells en el modelo SAP2000.</p>
        )}
        {grupos !== null && grupos.length > 0 && (
          <ul>
            {grupos.map((g) => (
              <li key={g.nombre}>
                <span>
                  {g.nombre} ({g.n_shells} shells)
                </span>{' '}
                <button
                  type="button"
                  onClick={() => void leerFundacion(g.nombre)}
                  disabled={trabajo !== null}
                >
                  Leer fundación
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {mensaje && (
        <p className="sap-fund-error" role="alert">
          {mensaje}
        </p>
      )}

      {trabajo && (
        <section className="sap-fund-progreso" aria-label="Lectura de la fundación">
          <p>Grupo: {trabajo.grupo}</p>
          <p role="status">
            {trabajo.estado
              ? `Etapa: ${trabajo.estado.etapa || '…'}`
              : 'Iniciando la lectura en SAP2000…'}
          </p>
          <div
            className="sap-fund-barra-fondo"
            role="progressbar"
            aria-label="Progreso de la lectura"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-valuetext={`${hechas} de ${total}`}
          >
            <div className="sap-fund-barra" style={{ width: `${pct}%` }} />
          </div>
          <p className="sap-fund-cifras">
            {hechas} / {total} · transcurrido {Math.round(trabajo.estado?.transcurrido_s ?? 0)} s
          </p>
          <button
            type="button"
            onClick={() => void cancelar()}
            disabled={!trabajo.job || trabajo.cancelando}
          >
            Cancelar
          </button>
        </section>
      )}

      {base && resumen && (
        <section className="sap-fund-edicion" aria-label="Geometría de la fundación">
          <p className="sap-fund-resumen">
            {resumen.zapatas} zapatas · {resumen.pedestales} pedestales · {resumen.areas} áreas
          </p>
          {base.zapatas.map((z, i) => {
            const incluida = incl.includes(i)
            const espesor = z.areas[0]?.espesor ?? null
            return (
              <article
                key={i}
                className={incluida ? 'sap-fund-zapata' : 'sap-fund-zapata sap-fund-excluida'}
                aria-label={`Zapata ${z.nombre}`}
              >
                <div className="sap-fund-cab">
                  <label>
                    <input type="checkbox" checked={incluida} onChange={() => alternarIncluir(i)} />{' '}
                    Incluir {z.nombre}
                  </label>
                  <label>
                    Espesor (mm){' '}
                    <CampoNumero
                      etiqueta={`Espesor de ${z.nombre} (mm)`}
                      valor={espesor}
                      onCambio={(mm) => aplicar((g) => setEspesorZapata(g, i, mm))}
                    />
                  </label>
                </div>
                {z.pedestales.length === 0 ? (
                  <p>Sin pedestales.</p>
                ) : (
                  <table>
                    <caption>Pedestales de {z.nombre}</caption>
                    <thead>
                      <tr>
                        <th scope="col">Frame</th>
                        <th scope="col">Largo (mm)</th>
                        <th scope="col">Ancho (mm)</th>
                        <th scope="col">Largo en X</th>
                        <th scope="col">Aviso</th>
                        <th scope="col">
                          <span className="sap-fund-sr">Acción</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {z.pedestales.map((p, j) => (
                        <tr key={j}>
                          <td>{p.frame}</td>
                          <td>
                            <CampoNumero
                              etiqueta={`Largo del pedestal ${p.frame}`}
                              valor={p.largo}
                              onCambio={(v) => aplicar((g) => setPedestal(g, i, j, { largo: v }))}
                            />
                          </td>
                          <td>
                            <CampoNumero
                              etiqueta={`Ancho del pedestal ${p.frame}`}
                              valor={p.ancho}
                              onCambio={(v) => aplicar((g) => setPedestal(g, i, j, { ancho: v }))}
                            />
                          </td>
                          <td>
                            <input
                              type="checkbox"
                              aria-label={`Largo en X del pedestal ${p.frame}`}
                              checked={p.largo_en_x}
                              onChange={(e) =>
                                aplicar((g) =>
                                  setPedestal(g, i, j, { largo_en_x: e.target.checked }),
                                )
                              }
                            />
                          </td>
                          <td>
                            {avisoDe(p) && (
                              <span className="sap-fund-aviso" role="note">
                                {avisoDe(p)}
                              </span>
                            )}
                          </td>
                          <td>
                            <button
                              type="button"
                              aria-label={`Quitar pedestal ${p.frame}`}
                              onClick={() => aplicar((g) => quitarPedestal(g, i, j))}
                            >
                              Quitar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </article>
            )
          })}
        </section>
      )}
    </div>
  )
}
