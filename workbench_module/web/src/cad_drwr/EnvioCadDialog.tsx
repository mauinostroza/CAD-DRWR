import { useEffect, useId, useRef, useState } from 'react'
import type { DibujoRespuesta } from './api'
import {
  MENSAJE_SIN_EMPAREJAR,
  enviarDibujo,
  estadoCad,
  obtenerCredenciales,
  type BridgeCreds,
  type EstadoCad,
  type EstadoEnvio,
  type ResumenEnvio,
} from './bridgeCad'
import './envio.css'

type Props = {
  dibujo: DibujoRespuesta | null
  nombre: string
  onCerrar: () => void
}

type EstadoPuente =
  | { tipo: 'comprobando' }
  | { tipo: 'sin_credenciales' }
  | { tipo: 'error'; mensaje: string }
  | { tipo: 'listo'; estado: EstadoCad }

type Envio =
  | { tipo: 'inactivo' }
  | { tipo: 'en_curso'; estado: EstadoEnvio }
  | { tipo: 'fallo_pick'; mensaje: string }
  | { tipo: 'error'; mensaje: string }
  | { tipo: 'listo'; resumen: ResumenEnvio }

const MAX_ERRORES_VISIBLES = 50
const SELECTOR_FOCO = 'button:not([disabled]), input:not([disabled]), summary'

function mensajeDe(e: unknown): string {
  return e instanceof Error ? e.message : 'Error desconocido.'
}

function formatearTiempo(segundos: number): string {
  const m = Math.floor(segundos / 60)
  const s = segundos % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** Diálogo modal de envío de un dibujo al CAD. Se monta al abrir y se desmonta al cerrar. */
export default function EnvioCadDialog({ dibujo, nombre, onCerrar }: Props) {
  if (!dibujo) return null
  return <DialogoEnvio dibujo={dibujo} nombre={nombre} onCerrar={onCerrar} />
}

function DialogoEnvio({
  dibujo,
  nombre,
  onCerrar,
}: {
  dibujo: DibujoRespuesta
  nombre: string
  onCerrar: () => void
}) {
  const idTitulo = useId()
  const dialogoRef = useRef<HTMLDivElement>(null)
  const credsRef = useRef<BridgeCreds | null>(null)
  const puenteCtrlRef = useRef<AbortController | null>(null)
  const envioCtrlRef = useRef<AbortController | null>(null)

  const [puente, setPuente] = useState<EstadoPuente>({ tipo: 'comprobando' })
  const [ubicar, setUbicar] = useState(true)
  const [envio, setEnvio] = useState<Envio>({ tipo: 'inactivo' })
  const [segundos, setSegundos] = useState(0)

  const total = dibujo.cad.length
  const enEspera = envio.tipo === 'en_curso' && envio.estado.fase === 'esperando_clic'
  const enCurso = envio.tipo === 'en_curso'
  const puedeCerrar = !enEspera
  const conectado = puente.tipo === 'listo' && puente.estado.conectado

  /** Lee credenciales y estado del CAD. Cada llamada anula la anterior. */
  function comprobar() {
    puenteCtrlRef.current?.abort()
    const ctrl = new AbortController()
    puenteCtrlRef.current = ctrl
    setPuente({ tipo: 'comprobando' })
    obtenerCredenciales()
      .then(async c => {
        if (ctrl.signal.aborted) return
        if (c.source === 'none') {
          credsRef.current = null
          setPuente({ tipo: 'sin_credenciales' })
          return
        }
        credsRef.current = c
        const estado = await estadoCad(c, ctrl.signal)
        if (!ctrl.signal.aborted) setPuente({ tipo: 'listo', estado })
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setPuente({ tipo: 'error', mensaje: mensajeDe(e) })
      })
  }

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null
    comprobar()
    return () => {
      puenteCtrlRef.current?.abort()
      envioCtrlRef.current?.abort()
      anterior?.focus?.()
    }
    // Sólo al montar: cada apertura monta un diálogo nuevo.
  }, [])

  // Si el botón enfocado desaparece (cambio de fase), el foco vuelve al diálogo.
  useEffect(() => {
    const d = dialogoRef.current
    if (d && !d.contains(document.activeElement)) d.focus()
  }, [envio.tipo])

  // Esc y Tab se atienden en el documento: el foco puede quedar en <body> al cambiar de fase.
  const atenderRef = useRef(atender)
  atenderRef.current = atender
  useEffect(() => {
    const manejar = (e: KeyboardEvent) => atenderRef.current(e)
    document.addEventListener('keydown', manejar)
    return () => document.removeEventListener('keydown', manejar)
  }, [])

  async function ejecutar(conUbicacion: boolean) {
    const creds = credsRef.current
    if (!creds) return
    const ctrl = new AbortController()
    envioCtrlRef.current = ctrl
    const inicio = Date.now()
    setSegundos(0)
    const reloj = setInterval(() => {
      setSegundos(Math.floor((Date.now() - inicio) / 1000))
    }, 1000)
    // El callback cambia la fase: el cast evita que TS la estreche a 'conectando'.
    let faseActual = 'conectando' as EstadoEnvio['fase']
    setEnvio({
      tipo: 'en_curso',
      estado: { fase: 'conectando', hechas: 0, total, mensaje: 'Comprobando el puente y el CAD…' },
    })
    try {
      const resumen = await enviarDibujo(creds, dibujo, {
        ubicarConClic: conUbicacion,
        signal: ctrl.signal,
        onEstado: estado => {
          faseActual = estado.fase
          if (!ctrl.signal.aborted) setEnvio({ tipo: 'en_curso', estado })
        },
      })
      if (!ctrl.signal.aborted) setEnvio({ tipo: 'listo', resumen })
    } catch (e) {
      if (ctrl.signal.aborted) {
        setEnvio({ tipo: 'error', mensaje: 'Envío cancelado.' })
      } else if (faseActual === 'esperando_clic') {
        setEnvio({ tipo: 'fallo_pick', mensaje: mensajeDe(e) })
      } else {
        setEnvio({ tipo: 'error', mensaje: mensajeDe(e) })
      }
    } finally {
      clearInterval(reloj)
      if (envioCtrlRef.current === ctrl) envioCtrlRef.current = null
    }
  }

  function cerrar() {
    if (!puedeCerrar) return
    envioCtrlRef.current?.abort()
    onCerrar()
  }

  function atender(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      cerrar()
      return
    }
    if (e.key !== 'Tab' || !dialogoRef.current) return
    const focos = Array.from(dialogoRef.current.querySelectorAll<HTMLElement>(SELECTOR_FOCO))
    if (focos.length === 0) return
    const primero = focos[0]
    const ultimo = focos[focos.length - 1]
    const activo = document.activeElement
    const fuera = !activo || !dialogoRef.current.contains(activo)
    if (e.shiftKey && (activo === primero || fuera)) {
      e.preventDefault()
      ultimo.focus()
    } else if (!e.shiftKey && (activo === ultimo || fuera)) {
      e.preventDefault()
      primero.focus()
    }
  }

  const hechas =
    envio.tipo === 'en_curso' ? envio.estado.hechas : envio.tipo === 'listo' ? total : 0
  const pct = total > 0 ? Math.round((hechas / total) * 100) : envio.tipo === 'listo' ? 100 : 0

  return (
    <div className="envio-cad-fondo">
      <div
        ref={dialogoRef}
        className="envio-cad"
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        tabIndex={-1}
      >
        <header className="envio-cad-cabecera">
          <h2 id={idTitulo}>Enviar a ZWCAD/AutoCAD</h2>
          <p className="envio-cad-nombre">{nombre}</p>
        </header>

        <section className="envio-cad-puente" aria-label="Estado del puente">
          {puente.tipo === 'comprobando' && <p role="status">Comprobando el puente…</p>}
          {puente.tipo === 'sin_credenciales' && (
            <p className="envio-cad-aviso" role="status">
              {MENSAJE_SIN_EMPAREJAR}
            </p>
          )}
          {puente.tipo === 'error' && (
            <p className="envio-cad-error" role="alert">
              {puente.mensaje}
            </p>
          )}
          {puente.tipo === 'listo' && puente.estado.conectado && (
            <p>
              Conectado: {puente.estado.programa ?? 'CAD'} · documento:{' '}
              {puente.estado.documento ?? '(ninguno)'}
            </p>
          )}
          {puente.tipo === 'listo' && !puente.estado.conectado && (
            <p className="envio-cad-error" role="alert">
              No hay CAD disponible: {puente.estado.detalle}
            </p>
          )}
          {(puente.tipo === 'error' || (puente.tipo === 'listo' && !conectado)) &&
            envio.tipo === 'inactivo' && (
              <button type="button" onClick={comprobar}>
                Comprobar de nuevo
              </button>
            )}
        </section>

        <div className="envio-cad-opciones">
          <label>
            <input
              type="checkbox"
              checked={ubicar}
              disabled={enCurso || puente.tipo !== 'listo'}
              onChange={e => setUbicar(e.target.checked)}
            />{' '}
            Ubicar con clic
          </label>
          <span>{total} entidades</span>
        </div>

        {envio.tipo === 'en_curso' && (
          <section className="envio-cad-progreso" aria-label="Progreso del envío">
            {enEspera ? (
              <p className="envio-cad-espera" role="status">
                Haga clic en la ventana de ZWCAD/AutoCAD para indicar el punto de inserción (Esc en
                el CAD cancela).
              </p>
            ) : (
              <p role="status">{envio.estado.mensaje}</p>
            )}
            <div
              className="envio-cad-barra-fondo"
              role="progressbar"
              aria-label="Progreso del envío"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
              aria-valuetext={`${hechas} de ${total} entidades`}
            >
              <div className="envio-cad-barra" style={{ width: `${pct}%` }} />
            </div>
            <p className="envio-cad-cifras">
              {hechas} / {total} ({pct}%) · Tiempo transcurrido: {formatearTiempo(segundos)}
            </p>
          </section>
        )}

        {envio.tipo === 'fallo_pick' && (
          <section className="envio-cad-error" role="alert">
            <p>No se pudo indicar el punto: {envio.mensaje}</p>
            <div className="envio-cad-acciones">
              <button type="button" onClick={() => void ejecutar(true)} disabled={!conectado}>
                Reintentar
              </button>
              <button type="button" onClick={() => void ejecutar(false)} disabled={!conectado}>
                Enviar sin ubicar (origen 0,0)
              </button>
            </div>
          </section>
        )}

        {envio.tipo === 'error' && (
          <p className="envio-cad-error" role="alert">
            {envio.mensaje}
          </p>
        )}

        {envio.tipo === 'listo' && (
          <section className="envio-cad-resumen" aria-label="Resumen del envío">
            <p role="status">{envio.resumen.resumen}</p>
            {envio.resumen.omitidas > 0 && (
              <details>
                <summary>
                  Entidades omitidas: {envio.resumen.omitidas}
                  {envio.resumen.errores.length > MAX_ERRORES_VISIBLES
                    ? ` (mostrando ${MAX_ERRORES_VISIBLES})`
                    : ''}
                </summary>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Índice</th>
                      <th scope="col">Tipo</th>
                      <th scope="col">Motivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {envio.resumen.errores.slice(0, MAX_ERRORES_VISIBLES).map(err => (
                      <tr key={`${err.indice}-${err.motivo}`}>
                        <td>{err.indice}</td>
                        <td>{err.tipo}</td>
                        <td>{err.motivo}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
          </section>
        )}

        <footer className="envio-cad-pie">
          {(envio.tipo === 'inactivo' || envio.tipo === 'error') && (
            <button type="button" onClick={() => void ejecutar(ubicar)} disabled={!conectado}>
              Enviar
            </button>
          )}
          {envio.tipo === 'en_curso' &&
            (envio.estado.fase === 'conectando' || envio.estado.fase === 'enviando') && (
              <button type="button" onClick={() => envioCtrlRef.current?.abort()}>
                Cancelar envío
              </button>
            )}
          <button type="button" onClick={cerrar} disabled={!puedeCerrar}>
            Cerrar
          </button>
        </footer>
      </div>
    </div>
  )
}
