import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  descargarDxf,
  descargarLote,
  listarModulos,
  pedirDibujo,
  type DibujoRespuesta,
} from './api'
import CadDrwrPage, { reiniciarCargaModulos } from './CadDrwrPage'
import type { ModuloInfo } from './tipos'
import { saveBlob } from '../lib_client'

vi.mock('./api', () => ({
  listarModulos: vi.fn(),
  pedirDibujo: vi.fn(),
  descargarDxf: vi.fn(),
  descargarLote: vi.fn(),
}))

vi.mock('../lib_client', () => ({ saveBlob: vi.fn() }))

vi.mock('./vista/exportar', async (importOriginal) => {
  const original = await importOriginal<typeof import('./vista/exportar')>()
  return { ...original, aPngBlob: vi.fn(async () => new Blob(['png'])) }
})

vi.mock('./vista/VistaSvg', async () => {
  const R = await import('react')
  return { VistaSvg: () => R.createElement('div', { 'data-testid': 'vista-svg' }) }
})

vi.mock('./SapFundacionPanel', async () => {
  const R = await import('react')
  return { default: () => R.createElement('p', null, 'Panel SAP (simulado)') }
})

vi.mock('./EnvioCadDialog', async () => {
  const R = await import('react')
  return { default: () => R.createElement('div', { role: 'dialog' }, 'Envío simulado') }
})

const MODULOS: ModuloInfo[] = [
  {
    id: 'placa_base',
    nombre: 'Placa base',
    interactivo: false,
    defaults: { perfil: 'W250X25', B: 440, escala: '1:50' },
    campos: [
      {
        key: 'B',
        label: 'Ancho B (mm)',
        kind: 'float',
        min: 100,
        max: 1000,
        value: 440,
        decimals: 0,
        step: 10,
        suffix: 'mm',
      },
    ],
  },
  {
    id: 'pedestal',
    nombre: 'Pedestal',
    interactivo: false,
    defaults: { b: 30, escala: '1:25' },
    campos: [
      {
        key: 'b',
        label: 'Ancho b (cm)',
        kind: 'int',
        min: 20,
        max: 200,
        value: 30,
        step: 5,
        suffix: 'cm',
      },
    ],
  },
  {
    id: 'fundacion_sap',
    nombre: 'Fundación SAP2000',
    interactivo: true,
    defaults: { escala: '1:50', espesor_default: 0 },
    campos: [],
  },
]

function dibujoRespuesta(modulo: string): DibujoRespuesta {
  return {
    th: 1,
    bounds: [0, 0, 100, 100],
    render: [
      { t: 'line', a: [0, 0], b: [100, 100], l: 'CONCRETO', w: 0 },
      { t: 'line', a: [0, 100], b: [100, 0], l: 'TEXTOS', w: 0 },
    ],
    cad: [],
    n_render: 2,
    n_cad: 0,
    modulo,
    hash: `h-${modulo}`,
    solapes: [],
  }
}

const esperarMs = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)))

function renderPagina(state: unknown = undefined) {
  const onState = vi.fn()
  render(<CadDrwrPage state={state} onState={onState} onReport={() => {}} />)
  return { onState }
}

async function campoB(): Promise<HTMLElement> {
  return screen.findByRole('spinbutton', { name: 'Ancho B (mm)' })
}

beforeEach(() => {
  vi.clearAllMocks()
  reiniciarCargaModulos()
  vi.mocked(listarModulos).mockResolvedValue(MODULOS)
  vi.mocked(pedirDibujo).mockImplementation(async (modulo) => dibujoRespuesta(modulo))
  vi.mocked(descargarDxf).mockResolvedValue(new Blob(['dxf']))
  vi.mocked(descargarLote).mockResolvedValue(new Blob(['zip']))
})

describe('CadDrwrPage', () => {
  it('carga los módulos, muestra el estado de carga y el formulario del módulo activo', async () => {
    renderPagina()
    expect(screen.getByRole('status')).toHaveTextContent('Cargando módulos')

    const nav = await screen.findByRole('navigation', { name: 'Módulos' })
    expect(nav).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pedestal' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Parámetros de Placa base' })).toBeInTheDocument()
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(1))
  })

  it('muestra un error con reintento si no se pueden cargar los módulos', async () => {
    vi.mocked(listarModulos).mockRejectedValue(new Error('Failed to fetch'))
    renderPagina()

    const alerta = await screen.findByRole('alert', {}, { timeout: 3000 })
    expect(alerta).toHaveTextContent('No se pudieron cargar los módulos: Failed to fetch')

    vi.mocked(listarModulos).mockResolvedValue(MODULOS)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('button', { name: 'Pedestal' })).toBeInTheDocument()
  })

  it('llama a pedirDibujo tras el debounce con los parámetros nuevos', async () => {
    const user = userEvent.setup()
    renderPagina()
    const campo = await campoB()
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(1))

    await user.clear(campo)
    await user.type(campo, '500')

    await waitFor(() =>
      expect(pedirDibujo).toHaveBeenLastCalledWith(
        'placa_base',
        expect.objectContaining({ B: 500 }),
        expect.objectContaining({ activa: false }),
        expect.anything(),
      ),
    )
  })

  it('envía la lámina activa al pedir el dibujo', async () => {
    const user = userEvent.setup()
    renderPagina()
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole('button', { name: 'Lámina' }))

    await waitFor(() =>
      expect(pedirDibujo).toHaveBeenLastCalledWith(
        'placa_base',
        expect.any(Object),
        expect.objectContaining({ activa: true }),
        expect.anything(),
      ),
    )
  })

  it('guarda una plantilla y la aplica tras deshacer', async () => {
    const user = userEvent.setup()
    renderPagina()
    const campo = await campoB()
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(1))
    await user.clear(campo)
    await user.type(campo, '500')
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(2))

    await user.click(screen.getByRole('button', { name: 'Plantillas' }))
    await user.type(screen.getByLabelText('Nombre de la plantilla'), 'Base ancha')
    await user.click(screen.getByRole('button', { name: 'Guardar actual' }))
    expect(
      screen.getByRole('button', { name: 'Aplicar plantilla Base ancha' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(campo).toHaveValue(440))

    await user.click(screen.getByRole('button', { name: 'Aplicar plantilla Base ancha' }))
    await waitFor(() =>
      expect(pedirDibujo).toHaveBeenLastCalledWith(
        'placa_base',
        expect.objectContaining({ B: 500 }),
        expect.anything(),
        expect.anything(),
      ),
    )
    await waitFor(() => expect(campo).toHaveValue(500))
  })

  it('deshace y rehace con Ctrl+Z y Ctrl+Y', async () => {
    const user = userEvent.setup()
    renderPagina()
    const campo = await campoB()
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(1))
    await user.clear(campo)
    await user.type(campo, '500')
    await waitFor(() => expect(campo).toHaveValue(500))

    // Con el foco fuera de un campo de texto, el atajo llega a la página.
    await user.click(screen.getByRole('button', { name: 'Ajustar' }))
    await user.keyboard('{Control>}z{/Control}')
    await waitFor(() => expect(campo).toHaveValue(440))

    await user.keyboard('{Control>}y{/Control}')
    await waitFor(() => expect(campo).toHaveValue(500))
  })

  it('exporta DXF con descargarDxf y guarda el archivo', async () => {
    const user = userEvent.setup()
    renderPagina()
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole('button', { name: 'Exportar' }))
    await user.click(screen.getByRole('button', { name: 'DXF' }))

    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'placa_base.dxf'))
    expect(descargarDxf).toHaveBeenCalledWith(
      'placa_base',
      expect.objectContaining({ B: 440 }),
      expect.objectContaining({ activa: false }),
    )
  })

  it('exporta el ZIP de todos los módulos sin el interactivo', async () => {
    const user = userEvent.setup()
    renderPagina()
    await waitFor(() => expect(pedirDibujo).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole('button', { name: 'Exportar' }))
    await user.click(screen.getByRole('button', { name: 'Todos los módulos (ZIP de DXF)' }))

    await waitFor(() =>
      expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'cad_drwr_lote.zip'),
    )
    const items = vi.mocked(descargarLote).mock.calls[0][0]
    expect(items.map((i) => i.modulo)).toEqual(['placa_base', 'pedestal'])
  })

  it('muestra el error del servidor en un aviso', async () => {
    vi.mocked(pedirDibujo).mockRejectedValueOnce(new Error('Dimensión inválida en la placa'))
    renderPagina()

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(
      'No se pudo actualizar el dibujo: Dimensión inválida en la placa',
    )
  })

  it('en un módulo interactivo sin geometría no llama al servidor', async () => {
    const user = userEvent.setup()
    renderPagina()
    await user.click(await screen.findByRole('button', { name: 'Fundación SAP2000' }))

    expect(await screen.findByText('Panel SAP (simulado)')).toBeInTheDocument()
    expect(screen.getByText(/Lea la geometría desde SAP2000/)).toBeInTheDocument()
    await esperarMs(300)
    const llamadas = vi.mocked(pedirDibujo).mock.calls
    expect(llamadas.some((c) => c[0] === 'fundacion_sap')).toBe(false)
  })

  it('guarda el estado con debounce mediante onState', async () => {
    const { onState } = renderPagina()
    await waitFor(() => expect(onState).toHaveBeenCalled(), { timeout: 1500 })

    expect(onState.mock.lastCall?.[0]).toMatchObject({ schema_version: 1, modulo: 'placa_base' })
  })
})
