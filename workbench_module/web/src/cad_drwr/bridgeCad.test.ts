import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DibujoRespuesta } from './api'
import {
  ErrorPuente,
  MENSAJE_ANTIGUO,
  TAM_LOTE,
  batchCad,
  enviarDibujo,
  estadoCad,
  type BridgeCreds,
  type EstadoEnvio,
} from './bridgeCad'
import type { EntCad } from './tipos'

const URL_BASE = 'http://127.0.0.1:8765'
const CREDS: BridgeCreds = { source: 'local', url: URL_BASE, token: 'tok-123' }
const RAIZ = '/v1/sap/actions/cad'

type Resp = { status: number; json?: unknown }
type Llamada = { ruta: string; body: Record<string, unknown>; auth: string | null }
type Manejador = (ruta: string, body: Record<string, unknown>) => Resp | Error | DOMException

function respuesta(r: Resp) {
  return {
    ok: r.status >= 200 && r.status < 300,
    status: r.status,
    json: async () => {
      if (r.json === undefined) throw new SyntaxError('sin cuerpo JSON')
      return r.json
    },
  }
}

/** Simula fetch; cada llamada se registra con su ruta, cuerpo y cabecera Authorization. */
function montarFetch(manejador: Manejador) {
  const llamadas: Llamada[] = []
  const fn = vi.fn(async (url: string, init: RequestInit) => {
    const ruta = url.slice(URL_BASE.length).replace(RAIZ, '')
    const body = JSON.parse(String(init.body)) as Record<string, unknown>
    const headers = init.headers as Record<string, string>
    llamadas.push({ ruta, body, auth: headers.Authorization ?? null })
    const r = manejador(ruta, body)
    // Un error lanzado (red caída, cancelación) no es una respuesta HTTP.
    if (!('status' in r)) throw r
    return respuesta(r)
  })
  vi.stubGlobal('fetch', fn)
  return { fn, llamadas, rutas: () => llamadas.map((l) => l.ruta) }
}

/** Respuestas por defecto de un envío correcto; `extra` sobrescribe rutas concretas. */
function ruteoOk(extra: Partial<Record<string, Manejador>> = {}): Manejador {
  return (ruta, body) => {
    if (extra[ruta]) return extra[ruta]!(ruta, body)
    switch (ruta) {
      case '/status':
        return {
          status: 200,
          json: {
            conectado: true,
            programa: 'ZWCAD',
            version: '2025',
            documento: 'plano.dwg',
            detalle: 'ZWCAD | versión 2025 | documento: plano.dwg',
          },
        }
      case '/pick':
        return { status: 200, json: { x: 10, y: -5 } }
      case '/draw/begin':
        return { status: 200, json: { sesion: 'S1', programa: 'ZWCAD', documento: 'plano.dwg' } }
      case '/draw/batch': {
        const ents = body.ents as unknown[]
        return { status: 200, json: { creadas: ents.length, omitidas: 0, errores: [] } }
      }
      case '/draw/end':
        return {
          status: 200,
          json: { documento: 'plano.dwg', creadas: 0, omitidas: 0, resumen: 'Resumen OK' },
        }
    }
    return { status: 404 }
  }
}

function dibujo(n: number, th = 3.5): DibujoRespuesta {
  const cad: EntCad[] = Array.from({ length: n }, (_, i) => ({
    t: 'line',
    a: [i, 0],
    b: [i, 1],
    l: 'CONCRETO',
    w: 0,
  }))
  return {
    th,
    bounds: null,
    render: [],
    cad,
    n_render: 0,
    n_cad: n,
    modulo: 'zapata',
    hash: 'h',
    solapes: [],
  }
}

async function errorDe(p: Promise<unknown>): Promise<ErrorPuente> {
  try {
    await p
  } catch (e) {
    if (e instanceof ErrorPuente) return e
    throw e
  }
  throw new Error('la promesa no fue rechazada')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('enviarDibujo: orquestación', () => {
  it('envía en lotes de 500 y termina con end (sin pick)', async () => {
    const { llamadas, rutas } = montarFetch(ruteoOk())
    const r = await enviarDibujo(CREDS, dibujo(1200), { ubicarConClic: false })

    expect(TAM_LOTE).toBe(500)
    expect(rutas()).toEqual([
      '/status',
      '/draw/begin',
      '/draw/batch',
      '/draw/batch',
      '/draw/batch',
      '/draw/end',
    ])
    const lotes = llamadas.filter((l) => l.ruta === '/draw/batch')
    expect(lotes.map((l) => (l.body.ents as unknown[]).length)).toEqual([500, 500, 200])
    expect(lotes.every((l) => l.body.sesion === 'S1')).toBe(true)

    const begin = llamadas.find((l) => l.ruta === '/draw/begin')!
    expect(begin.body).toEqual({ confirmed: true, n_total: 1200, th: 3.5 })
    expect(llamadas.find((l) => l.ruta === '/draw/end')!.body).toEqual({ sesion: 'S1' })
    expect(r.documento).toBe('plano.dwg')
    expect(r.resumen).toBe('Resumen OK')
  })

  it('envía el Bearer del puente en cada llamada', async () => {
    const { llamadas } = montarFetch(ruteoOk())
    await enviarDibujo(CREDS, dibujo(3), { ubicarConClic: false })
    expect(llamadas.every((l) => l.auth === 'Bearer tok-123')).toBe(true)
  })

  it('con ubicarConClic envía el origen del pick en begin', async () => {
    const { llamadas, rutas } = montarFetch(ruteoOk())
    const fases: EstadoEnvio['fase'][] = []
    await enviarDibujo(CREDS, dibujo(2), {
      ubicarConClic: true,
      onEstado: (e) => fases.push(e.fase),
    })
    expect(rutas()).toContain('/pick')
    expect(llamadas.find((l) => l.ruta === '/draw/begin')!.body.origen).toEqual([10, -5])
    expect(fases).toEqual([
      'conectando',
      'esperando_clic',
      'enviando',
      'enviando',
      'finalizando',
      'listo',
    ])
  })

  it('sin pick no envía origen', async () => {
    const { llamadas } = montarFetch(ruteoOk())
    await enviarDibujo(CREDS, dibujo(2), { ubicarConClic: false })
    expect('origen' in llamadas.find((l) => l.ruta === '/draw/begin')!.body).toBe(false)
  })

  it('acumula errores de cada lote con índice global (offset)', async () => {
    let n = 0
    const manejador = ruteoOk({
      '/draw/batch': (_r, body) => {
        n += 1
        const ents = body.ents as unknown[]
        const errores =
          n === 2
            ? [{ indice: 3, tipo: 'line', motivo: 'Capa bloqueada' }]
            : n === 3
              ? [{ indice: 199, tipo: 'text', motivo: 'Fuente no encontrada' }]
              : []
        return {
          status: 200,
          json: { creadas: ents.length - errores.length, omitidas: errores.length, errores },
        }
      },
      '/draw/end': () => ({
        status: 200,
        json: { documento: 'plano.dwg', creadas: 1198, omitidas: 2, resumen: 'con omitidas' },
      }),
    })
    montarFetch(manejador)
    const r = await enviarDibujo(CREDS, dibujo(1200), { ubicarConClic: false })
    expect(r.errores).toEqual([
      { indice: 503, tipo: 'line', motivo: 'Capa bloqueada' },
      { indice: 1199, tipo: 'text', motivo: 'Fuente no encontrada' },
    ])
    expect(r.omitidas).toBe(2)
  })

  it('cancelar tras el primer lote llama a end para liberar la sesión', async () => {
    const ctrl = new AbortController()
    let lotes = 0
    const { llamadas } = montarFetch(
      ruteoOk({
        '/draw/batch': (_r, body) => {
          lotes += 1
          if (lotes === 1) ctrl.abort()
          return {
            status: 200,
            json: { creadas: (body.ents as unknown[]).length, omitidas: 0, errores: [] },
          }
        },
      }),
    )
    const err = await enviarDibujo(CREDS, dibujo(1200), {
      ubicarConClic: false,
      signal: ctrl.signal,
    }).catch((e: unknown) => e)
    expect(err).toMatchObject({ name: 'AbortError' })
    expect(lotes).toBe(1)
    const fin = llamadas.filter((l) => l.ruta === '/draw/end')
    expect(fin).toHaveLength(1)
    expect(fin[0].body).toEqual({ sesion: 'S1' })
  })

  it('cancelar antes de begin no abre sesión', async () => {
    const ctrl = new AbortController()
    ctrl.abort()
    const { rutas } = montarFetch(ruteoOk())
    await expect(
      enviarDibujo(CREDS, dibujo(5), { ubicarConClic: false, signal: ctrl.signal }),
    ).rejects.toMatchObject({ name: 'AbortError' })
    expect(rutas()).not.toContain('/draw/begin')
  })

  it('un error de lote (422) se propaga como validacion y libera la sesión', async () => {
    montarFetch(
      ruteoOk({
        '/draw/batch': () => ({
          status: 422,
          json: {
            detail: [
              { loc: ['body', 'ents', 0, 'l'], msg: 'Capa desconocida: X', type: 'value_error' },
            ],
          },
        }),
      }),
    )
    const err = await errorDe(enviarDibujo(CREDS, dibujo(4), { ubicarConClic: false }))
    expect(err.codigo).toBe('validacion')
    expect(err.message).toBe('ents.0.l: Capa desconocida: X')
  })

  it('si el CAD no está conectado no envía begin y responde con el motivo', async () => {
    const { rutas } = montarFetch(
      ruteoOk({
        '/status': () => ({
          status: 200,
          json: {
            conectado: false,
            programa: null,
            version: null,
            documento: null,
            detalle: 'No hay ZWCAD abierto',
          },
        }),
      }),
    )
    const err = await errorDe(enviarDibujo(CREDS, dibujo(4), { ubicarConClic: false }))
    expect(err.codigo).toBe('cad')
    expect(err.message).toBe('No hay ZWCAD abierto')
    expect(rutas()).not.toContain('/draw/begin')
  })

  it('error del pick no abre sesión y conserva el texto del CAD', async () => {
    const { rutas } = montarFetch(
      ruteoOk({
        '/pick': () => ({ status: 409, json: { detail: 'Selección de punto cancelada.' } }),
      }),
    )
    const err = await errorDe(enviarDibujo(CREDS, dibujo(4), { ubicarConClic: true }))
    expect(err.codigo).toBe('cad')
    expect(err.message).toBe('Selección de punto cancelada.')
    expect(rutas()).not.toContain('/draw/begin')
  })

  it('sin credenciales falla como sin_puente sin tocar la red', async () => {
    const { fn } = montarFetch(ruteoOk())
    const err = await errorDe(enviarDibujo({ source: 'none' }, dibujo(2), { ubicarConClic: false }))
    expect(err.codigo).toBe('sin_puente')
    expect(fn).not.toHaveBeenCalled()
  })
})

describe('mapeo de errores HTTP', () => {
  it('401 -> sesion', async () => {
    montarFetch(() => ({ status: 401, json: { detail: 'Not authenticated' } }))
    const err = await errorDe(estadoCad(CREDS))
    expect(err.codigo).toBe('sesion')
    expect(err.estado).toBe(401)
  })

  it('404 -> antiguo con el mensaje fijo de actualización', async () => {
    montarFetch(() => ({ status: 404, json: { detail: 'Not Found' } }))
    const err = await errorDe(estadoCad(CREDS))
    expect(err.codigo).toBe('antiguo')
    expect(err.message).toBe('Su SAP2000Bridge es anterior a este módulo; actualice el puente.')
    expect(err.message).toBe(MENSAJE_ANTIGUO)
  })

  it('409 -> cad con el detalle real del servidor', async () => {
    montarFetch(() => ({
      status: 409,
      json: { detail: 'La sesión de dibujo venció; vuelva a enviar' },
    }))
    const err = await errorDe(batchCad(CREDS, { sesion: 'X', ents: [] }))
    expect(err.codigo).toBe('cad')
    expect(err.message).toBe('La sesión de dibujo venció; vuelva a enviar')
  })

  it('422 -> validacion con los campos indicados por el servidor', async () => {
    montarFetch(() => ({
      status: 422,
      json: {
        detail: [{ loc: ['body', 'n_total'], msg: 'Debe ser menor o igual que 20000', type: 'x' }],
      },
    }))
    const err = await errorDe(estadoCad(CREDS))
    expect(err.codigo).toBe('validacion')
    expect(err.message).toBe('n_total: Debe ser menor o igual que 20000')
  })

  it('otros estados -> otro con el texto del servidor o el código', async () => {
    montarFetch(() => ({ status: 500, json: { detail: 'Fallo interno' } }))
    const err = await errorDe(estadoCad(CREDS))
    expect(err.codigo).toBe('otro')
    expect(err.message).toBe('Fallo interno')

    montarFetch(() => ({ status: 503 }))
    const sin = await errorDe(estadoCad(CREDS))
    expect(sin.codigo).toBe('otro')
    expect(sin.message).toContain('503')
  })

  it('red caída (fetch rechaza) -> sin_puente', async () => {
    montarFetch(() => new TypeError('Failed to fetch'))
    const err = await errorDe(estadoCad(CREDS))
    expect(err.codigo).toBe('sin_puente')
    expect(err.message).toContain('127.0.0.1:8765')
  })

  it('una cancelación no se convierte en sin_puente', async () => {
    const ctrl = new AbortController()
    montarFetch(() => new DOMException('abort', 'AbortError'))
    const e = await estadoCad(CREDS, ctrl.signal).catch((x: unknown) => x)
    expect(e).toMatchObject({ name: 'AbortError' })
  })

  it('sin credenciales -> sin_puente y sin llamadas', async () => {
    const { fn } = montarFetch(() => ({ status: 200, json: {} }))
    const err = await errorDe(estadoCad({ source: 'none' }))
    expect(err.codigo).toBe('sin_puente')
    expect(err.message).toContain('Abra SAP2000Bridge')
    expect(fn).not.toHaveBeenCalled()
  })
})
