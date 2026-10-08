import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { DibujoRespuesta } from './api'
import EnvioCadDialog from './EnvioCadDialog'
import {
  ErrorPuente,
  enviarDibujo,
  estadoCad,
  obtenerCredenciales,
  type BridgeCreds,
  type ResumenEnvio,
} from './bridgeCad'

vi.mock('./bridgeCad', async importOriginal => {
  const real = await importOriginal<typeof import('./bridgeCad')>()
  return {
    ...real,
    obtenerCredenciales: vi.fn(),
    estadoCad: vi.fn(),
    enviarDibujo: vi.fn(),
  }
})

const CREDS: BridgeCreds = { source: 'local', url: 'http://127.0.0.1:8765', token: 't' }
const ESTADO_OK = {
  conectado: true,
  programa: 'ZWCAD',
  version: '2025',
  documento: 'plano.dwg',
  detalle: 'ZWCAD | versión 2025 | documento: plano.dwg',
}

function dibujo(n: number): DibujoRespuesta {
  return {
    th: 3.5,
    bounds: null,
    render: [],
    cad: Array.from({ length: n }, (_, i) => ({ t: 'line', a: [i, 0], b: [i, 1], l: 'CONCRETO', w: 0 })),
    n_render: 0,
    n_cad: n,
    modulo: 'zapata',
    hash: 'h',
    solapes: [],
  }
}

function resumen(omitidas = 0, errores: ResumenEnvio['errores'] = []): ResumenEnvio {
  return {
    programa: 'ZWCAD',
    documento: 'plano.dwg',
    creadas: 1000 - omitidas,
    omitidas,
    resumen: `ZWCAD — documento: plano.dwg — ${1000 - omitidas} entidades creadas, ${omitidas} omitidas`,
    errores,
  }
}

const TEXTO_ESPERA = /Haga clic en la ventana de ZWCAD\/AutoCAD para indicar el punto de inserción/

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(obtenerCredenciales).mockResolvedValue(CREDS)
  vi.mocked(estadoCad).mockResolvedValue(ESTADO_OK)
})

describe('EnvioCadDialog', () => {
  it('no renderiza nada sin dibujo', () => {
    render(<EnvioCadDialog dibujo={null} nombre="Z1" onCerrar={() => undefined} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('sin credenciales guía para emparejar y no permite enviar', async () => {
    vi.mocked(obtenerCredenciales).mockResolvedValue({ source: 'none' })
    render(<EnvioCadDialog dibujo={dibujo(10)} nombre="Z1" onCerrar={() => undefined} />)

    expect(
      await screen.findByText(/Abra SAP2000Bridge y use el emparejamiento del módulo SAP2000 del Workbench/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled()
    expect(estadoCad).not.toHaveBeenCalled()
  })

  it('muestra el estado del CAD al abrir y es un diálogo modal', async () => {
    render(<EnvioCadDialog dibujo={dibujo(10)} nombre="Zapata Z1" onCerrar={() => undefined} />)

    const dlg = screen.getByRole('dialog')
    expect(dlg).toHaveAttribute('aria-modal', 'true')
    expect(await screen.findByText(/Conectado: ZWCAD · documento: plano.dwg/)).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Ubicar con clic' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeEnabled()
  })

  it('flujo feliz: espera de clic, progreso real y resumen', async () => {
    let darClic!: () => void
    const clic = new Promise<void>(r => (darClic = r))
    let terminar!: () => void
    const fin = new Promise<void>(r => (terminar = r))
    vi.mocked(enviarDibujo).mockImplementation(async (_c, _d, op) => {
      op.onEstado?.({ fase: 'esperando_clic', hechas: 0, total: 1000, mensaje: '' })
      await clic
      op.onEstado?.({ fase: 'enviando', hechas: 500, total: 1000, mensaje: 'Enviadas 500 de 1000.' })
      await fin
      return resumen()
    })
    const onCerrar = vi.fn()
    const user = userEvent.setup()
    render(<EnvioCadDialog dibujo={dibujo(1000)} nombre="Z1" onCerrar={onCerrar} />)

    await user.click(await screen.findByRole('button', { name: 'Enviar' }))

    expect(await screen.findByText(TEXTO_ESPERA)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeDisabled()

    // Esc no cierra mientras se espera el clic.
    await user.keyboard('{Escape}')
    expect(onCerrar).not.toHaveBeenCalled()

    darClic()
    const barra = await screen.findByRole('progressbar')
    await waitFor(() => expect(barra).toHaveAttribute('aria-valuenow', '50'))
    expect(screen.getByText(/500 \/ 1000 \(50%\)/)).toBeInTheDocument()

    terminar()
    expect(await screen.findByText(/1000 entidades creadas, 0 omitidas/)).toBeInTheDocument()
    expect(screen.queryByText(/Entidades omitidas/)).toBeNull()
    expect(enviarDibujo).toHaveBeenCalledWith(CREDS, expect.anything(), expect.objectContaining({ ubicarConClic: true }))
  })

  it('muestra la lista plegable de entidades omitidas', async () => {
    vi.mocked(enviarDibujo).mockResolvedValue(
      resumen(2, [
        { indice: 503, tipo: 'line', motivo: 'Capa bloqueada' },
        { indice: 1199, tipo: 'text', motivo: 'Fuente no encontrada' },
      ]),
    )
    const user = userEvent.setup()
    render(<EnvioCadDialog dibujo={dibujo(1000)} nombre="Z1" onCerrar={() => undefined} />)
    await user.click(await screen.findByRole('button', { name: 'Enviar' }))

    expect(await screen.findByText('Entidades omitidas: 2')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '503' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Fuente no encontrada' })).toBeInTheDocument()
  })

  it('pick fallido: muestra el texto exacto y permite reintentar con clic', async () => {
    vi.mocked(enviarDibujo)
      .mockImplementationOnce(async (_c, _d, op) => {
        op.onEstado?.({ fase: 'esperando_clic', hechas: 0, total: 4, mensaje: '' })
        throw new ErrorPuente('cad', 'Selección de punto cancelada.')
      })
      .mockResolvedValueOnce(resumen())
    const user = userEvent.setup()
    render(<EnvioCadDialog dibujo={dibujo(4)} nombre="Z1" onCerrar={() => undefined} />)
    await user.click(await screen.findByRole('button', { name: 'Enviar' }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent('No se pudo indicar el punto: Selección de punto cancelada.')

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText(/1000 entidades creadas/)).toBeInTheDocument()
    expect(vi.mocked(enviarDibujo).mock.calls[1][2].ubicarConClic).toBe(true)
  })

  it('pick fallido: "Enviar sin ubicar" envía sin clic', async () => {
    vi.mocked(enviarDibujo)
      .mockImplementationOnce(async (_c, _d, op) => {
        op.onEstado?.({ fase: 'esperando_clic', hechas: 0, total: 4, mensaje: '' })
        throw new ErrorPuente('cad', 'Selección de punto cancelada.')
      })
      .mockResolvedValueOnce(resumen())
    const user = userEvent.setup()
    render(<EnvioCadDialog dibujo={dibujo(4)} nombre="Z1" onCerrar={() => undefined} />)
    await user.click(await screen.findByRole('button', { name: 'Enviar' }))
    await user.click(await screen.findByRole('button', { name: 'Enviar sin ubicar (origen 0,0)' }))

    expect(await screen.findByText(/1000 entidades creadas/)).toBeInTheDocument()
    expect(vi.mocked(enviarDibujo).mock.calls[1][2].ubicarConClic).toBe(false)
  })

  it('Esc cierra el diálogo cuando no se espera el clic', async () => {
    const onCerrar = vi.fn()
    const user = userEvent.setup()
    render(<EnvioCadDialog dibujo={dibujo(4)} nombre="Z1" onCerrar={onCerrar} />)
    await screen.findByText(/Conectado/)
    await user.keyboard('{Escape}')
    expect(onCerrar).toHaveBeenCalledTimes(1)
  })

  it('un error que no es de pick muestra el mensaje y permite volver a enviar', async () => {
    vi.mocked(enviarDibujo).mockRejectedValueOnce(new ErrorPuente('validacion', 'ents.0.l: Capa desconocida: X'))
    const user = userEvent.setup()
    render(<EnvioCadDialog dibujo={dibujo(4)} nombre="Z1" onCerrar={() => undefined} />)
    await user.click(await screen.findByRole('button', { name: 'Enviar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Capa desconocida: X')
    expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeEnabled()
  })
})
