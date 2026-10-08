import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  cancelarFundacion,
  estadoFundacion,
  gruposSap,
  iniciarFundacion,
  obtenerCredenciales,
  type BridgeCreds,
} from './bridgeCad'
import SapFundacionPanel from './SapFundacionPanel'

vi.mock('./bridgeCad', async (importOriginal) => {
  const real = await importOriginal<typeof import('./bridgeCad')>()
  return {
    ...real,
    obtenerCredenciales: vi.fn(),
    gruposSap: vi.fn(),
    iniciarFundacion: vi.fn(),
    estadoFundacion: vi.fn(),
    cancelarFundacion: vi.fn(),
  }
})

const CREDS: BridgeCreds = { source: 'paired', url: 'http://127.0.0.1:8765', token: 't' }

function pedestal(frame: string, extra: Record<string, unknown> = {}) {
  return {
    frame,
    largo: 400,
    ancho: 300,
    largo_en_x: true,
    centro: [100, 100],
    punto_pie: 'P1',
    aproximado: false,
    motivo_aviso: '',
    ...extra,
  }
}

function zapata(nombre: string, pedestales: ReturnType<typeof pedestal>[], nAreas = 1) {
  return {
    nombre,
    areas: Array.from({ length: nAreas }, (_, k) => ({
      nombre: `${nombre}-A${k}`,
      seccion: 'S',
      espesor: 200,
      pts_nombres: [],
      pts: [[0, 0, 0]],
      pts_malla: [],
    })),
    contorno: [
      [0, 0],
      [2000, 0],
      [2000, 1500],
    ],
    pedestales,
  }
}

function fixture() {
  return {
    nombre: 'G1',
    zapatas: [
      zapata('Z1', [pedestal('FZ1a'), pedestal('FZ1b', { largo_en_x: false })], 2),
      zapata('Z2', []),
      zapata('Z3', [pedestal('FZ3a', { aproximado: true, motivo_aviso: 'Frame no ortogonal' })]),
    ],
  }
}

/** Deja correr las promesas ya resueltas y los temporizadores pedidos. */
async function turno(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(obtenerCredenciales).mockResolvedValue(CREDS)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('SapFundacionPanel: lectura', () => {
  it('lista sólo los grupos con shells', async () => {
    vi.mocked(gruposSap).mockResolvedValue({
      grupos: [
        { nombre: 'Fund', n_shells: 4 },
        { nombre: 'Vacio', n_shells: 0 },
      ],
    })
    const user = userEvent.setup()
    render(<SapFundacionPanel onGeom={() => undefined} />)
    await user.click(screen.getByRole('button', { name: 'Leer grupos' }))

    expect(await screen.findByText('Fund (4 shells)')).toBeInTheDocument()
    expect(screen.queryByText(/Vacio/)).toBeNull()
    expect(screen.getAllByRole('button', { name: 'Leer fundación' })).toHaveLength(1)
  })

  it('sin credenciales muestra la guía de emparejamiento', async () => {
    vi.mocked(obtenerCredenciales).mockResolvedValue({ source: 'none' })
    const user = userEvent.setup()
    render(<SapFundacionPanel onGeom={() => undefined} />)
    await user.click(screen.getByRole('button', { name: 'Leer grupos' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Abra SAP2000Bridge/)
    expect(gruposSap).not.toHaveBeenCalled()
  })

  it('sondea cada segundo y llama a onGeom al terminar', async () => {
    vi.useFakeTimers()
    const resultado = fixture()
    vi.mocked(gruposSap).mockResolvedValue({ grupos: [{ nombre: 'Fund', n_shells: 4 }] })
    vi.mocked(iniciarFundacion).mockResolvedValue({ job: 'J1' })
    vi.mocked(estadoFundacion)
      .mockResolvedValueOnce({
        estado: 'en_curso',
        etapa: 'Leyendo áreas',
        hechas: 2,
        total: 10,
        transcurrido_s: 1,
      })
      .mockResolvedValueOnce({
        estado: 'listo',
        etapa: '',
        hechas: 10,
        total: 10,
        transcurrido_s: 3,
        resultado,
      })
    const onGeom = vi.fn()
    render(<SapFundacionPanel onGeom={onGeom} />)

    fireEvent.click(screen.getByRole('button', { name: 'Leer grupos' }))
    await turno()
    fireEvent.click(screen.getByRole('button', { name: 'Leer fundación' }))
    await turno()

    expect(iniciarFundacion).toHaveBeenCalledWith(CREDS, 'Fund')
    expect(estadoFundacion).not.toHaveBeenCalled()

    await turno(1000)
    expect(estadoFundacion).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).toHaveTextContent('Etapa: Leyendo áreas')
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '20')
    expect(onGeom).not.toHaveBeenCalled()

    await turno(1000)
    expect(estadoFundacion).toHaveBeenCalledTimes(2)
    expect(estadoFundacion).toHaveBeenLastCalledWith(CREDS, 'J1')
    expect(onGeom).toHaveBeenCalledWith(resultado)
    expect(screen.queryByRole('progressbar')).toBeNull()

    // Ya no hay sondeo pendiente.
    await turno(3000)
    expect(estadoFundacion).toHaveBeenCalledTimes(2)
  })

  it('cancelar envía la cancelación y muestra el resultado cancelado', async () => {
    vi.useFakeTimers()
    vi.mocked(gruposSap).mockResolvedValue({ grupos: [{ nombre: 'Fund', n_shells: 4 }] })
    vi.mocked(iniciarFundacion).mockResolvedValue({ job: 'J1' })
    vi.mocked(estadoFundacion)
      .mockResolvedValueOnce({
        estado: 'en_curso',
        etapa: 'Leyendo',
        hechas: 1,
        total: 4,
        transcurrido_s: 1,
      })
      .mockResolvedValueOnce({
        estado: 'cancelado',
        etapa: 'Leyendo',
        hechas: 1,
        total: 4,
        transcurrido_s: 2,
      })
    vi.mocked(cancelarFundacion).mockResolvedValue({ cancelado: true })
    const onGeom = vi.fn()
    render(<SapFundacionPanel onGeom={onGeom} />)

    fireEvent.click(screen.getByRole('button', { name: 'Leer grupos' }))
    await turno()
    fireEvent.click(screen.getByRole('button', { name: 'Leer fundación' }))
    await turno()
    await turno(1000)

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    await turno()
    expect(cancelarFundacion).toHaveBeenCalledWith(CREDS, 'J1')

    await turno(1000)
    expect(screen.getByRole('alert')).toHaveTextContent('Lectura cancelada.')
    expect(onGeom).not.toHaveBeenCalled()
  })

  it('un job en error muestra el mensaje del puente', async () => {
    vi.useFakeTimers()
    vi.mocked(gruposSap).mockResolvedValue({ grupos: [{ nombre: 'Fund', n_shells: 4 }] })
    vi.mocked(iniciarFundacion).mockResolvedValue({ job: 'J1' })
    vi.mocked(estadoFundacion).mockResolvedValueOnce({
      estado: 'error',
      etapa: 'Leyendo',
      hechas: 0,
      total: 4,
      transcurrido_s: 1,
      error: 'SAP2000 no tiene modelo abierto',
    })
    const onGeom = vi.fn()
    render(<SapFundacionPanel onGeom={onGeom} />)

    fireEvent.click(screen.getByRole('button', { name: 'Leer grupos' }))
    await turno()
    fireEvent.click(screen.getByRole('button', { name: 'Leer fundación' }))
    await turno()
    await turno(1000)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'No se pudo leer la fundación: SAP2000 no tiene modelo abierto',
    )
    expect(onGeom).not.toHaveBeenCalled()
  })

  it('al desmontarse deja de sondear', async () => {
    vi.useFakeTimers()
    vi.mocked(gruposSap).mockResolvedValue({ grupos: [{ nombre: 'Fund', n_shells: 4 }] })
    vi.mocked(iniciarFundacion).mockResolvedValue({ job: 'J1' })
    vi.mocked(estadoFundacion).mockResolvedValue({
      estado: 'en_curso',
      etapa: 'Leyendo',
      hechas: 0,
      total: 4,
      transcurrido_s: 0,
    })
    const { unmount } = render(<SapFundacionPanel onGeom={() => undefined} />)
    fireEvent.click(screen.getByRole('button', { name: 'Leer grupos' }))
    await turno()
    fireEvent.click(screen.getByRole('button', { name: 'Leer fundación' }))
    await turno()
    unmount()
    await turno(5000)
    expect(estadoFundacion).not.toHaveBeenCalled()
  })
})

describe('SapFundacionPanel: edición', () => {
  it('editar el espesor llama a onGeom con la geometría cambiada y el contorno intacto', async () => {
    const user = userEvent.setup()
    const original = fixture()
    const onGeom = vi.fn()
    render(<SapFundacionPanel onGeom={onGeom} geomActual={original} />)

    const espesor = screen.getByRole('spinbutton', { name: 'Espesor de Z1 (mm)' })
    await user.clear(espesor)
    await user.type(espesor, '350')

    const ultima = onGeom.mock.calls.at(-1)![0] as typeof original
    expect(ultima.zapatas[0].areas.map((a) => a.espesor)).toEqual([350, 350])
    expect(ultima.zapatas[0].contorno).toEqual(original.zapatas[0].contorno)
    expect(original.zapatas[0].areas[0].espesor).toBe(200)
  })

  it('editar el ancho y la orientación de un pedestal', async () => {
    const user = userEvent.setup()
    const onGeom = vi.fn()
    render(<SapFundacionPanel onGeom={onGeom} geomActual={fixture()} />)

    const ancho = screen.getByRole('spinbutton', { name: 'Ancho del pedestal FZ1a' })
    await user.clear(ancho)
    await user.type(ancho, '450')
    await user.click(screen.getByRole('checkbox', { name: 'Largo en X del pedestal FZ1a' }))

    const ultima = onGeom.mock.calls.at(-1)![0] as ReturnType<typeof fixture>
    expect(ultima.zapatas[0].pedestales[0]).toMatchObject({ ancho: 450, largo_en_x: false })
  })

  it('quitar un pedestal lo elimina de la geometría emitida', async () => {
    const user = userEvent.setup()
    const onGeom = vi.fn()
    render(<SapFundacionPanel onGeom={onGeom} geomActual={fixture()} />)
    await user.click(screen.getByRole('button', { name: 'Quitar pedestal FZ1a' }))

    const ultima = onGeom.mock.calls.at(-1)![0] as ReturnType<typeof fixture>
    expect(ultima.zapatas[0].pedestales.map((p) => p.frame)).toEqual(['FZ1b'])
  })

  it('excluir una zapata emite sólo las incluidas y la exclusión se conserva al editar', async () => {
    const user = userEvent.setup()
    const onGeom = vi.fn()
    render(<SapFundacionPanel onGeom={onGeom} geomActual={fixture()} />)

    await user.click(screen.getByRole('checkbox', { name: 'Incluir Z2' }))
    let emitida = onGeom.mock.calls.at(-1)![0] as ReturnType<typeof fixture>
    expect(emitida.zapatas.map((z) => z.nombre)).toEqual(['Z1', 'Z3'])

    const espesor = screen.getByRole('spinbutton', { name: 'Espesor de Z1 (mm)' })
    await user.clear(espesor)
    await user.type(espesor, '300')
    emitida = onGeom.mock.calls.at(-1)![0] as ReturnType<typeof fixture>
    expect(emitida.zapatas.map((z) => z.nombre)).toEqual(['Z1', 'Z3'])
    expect(emitida.zapatas[0].areas[0].espesor).toBe(300)
  })

  it('muestra los avisos del puente por pedestal', () => {
    render(<SapFundacionPanel onGeom={() => undefined} geomActual={fixture()} />)
    expect(screen.getByRole('note')).toHaveTextContent('Frame no ortogonal')
  })
})
