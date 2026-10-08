import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Formulario } from './Formulario'
import type { Campo, ModuloInfo, Params } from './tipos'

const campos: Campo[] = [
  {
    key: 'preset',
    label: 'Distribución longitudinal',
    kind: 'combo',
    options: ['Total anterior', 'Por caras', 'Referencia 20'],
    value: 'Total anterior',
  },
  {
    key: 'b',
    label: 'Ancho sección b (cm)',
    kind: 'float',
    min: 20,
    max: 200,
    value: 30,
    decimals: 1,
    step: 5,
    suffix: '',
  },
  {
    key: 'h',
    label: 'Alto sección h (cm)',
    kind: 'float',
    min: 20,
    max: 200,
    value: 30,
    decimals: 1,
    step: 5,
    suffix: '',
  },
  {
    key: 'n_sup',
    label: 'Barras superiores (incl. esquinas)',
    kind: 'int',
    min: 2,
    max: 20,
    value: 7,
    step: 1,
    suffix: '',
  },
  {
    key: 'largo_barra',
    label: 'Largo barra B1 (m)',
    kind: 'float',
    min: 0.5,
    max: 12,
    value: 3.2,
    decimals: 2,
    step: 0.1,
    suffix: ' m',
  },
  {
    key: 'cuadro',
    label: 'Cuadro de despiece',
    kind: 'chk',
    value: true,
  },
]

const pedestal: ModuloInfo = {
  id: 'pedestal',
  nombre: 'Pedestal',
  campos,
  defaults: {},
  interactivo: false,
}

const valoresBase: Params = {
  preset: 'Total anterior',
  modo_b1: 'Según elevación',
  b: 30,
  h: 30,
  r: 4,
  n_barras: '8',
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
  largo_barra: 3.2,
  escala: '1:25',
  _escala: 2.5,
}

describe('Formulario (pedestal)', () => {
  it('al elegir "Referencia 20" llama a onCambio con b=55 y h=40', async () => {
    const user = userEvent.setup()
    const onCambio = vi.fn()
    render(<Formulario modulo={pedestal} valores={valoresBase} onCambio={onCambio} />)

    await user.selectOptions(screen.getByLabelText('Distribución longitudinal'), 'Referencia 20')

    expect(onCambio).toHaveBeenCalledTimes(1)
    const nuevos = onCambio.mock.calls[0][0] as Params
    expect(nuevos.preset).toBe('Referencia 20')
    expect(nuevos.b).toBe(55)
    expect(nuevos.h).toBe(40)
  })

  it('n_sup queda deshabilitado en "Total anterior" y habilitado en "Por caras"', () => {
    const { unmount } = render(
      <Formulario modulo={pedestal} valores={valoresBase} onCambio={vi.fn()} />,
    )
    expect(screen.getByLabelText('Barras superiores (incl. esquinas)')).toBeDisabled()
    unmount()

    render(
      <Formulario
        modulo={pedestal}
        valores={{ ...valoresBase, preset: 'Por caras' }}
        onCambio={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('Barras superiores (incl. esquinas)')).toBeEnabled()
  })

  it('un valor fuera de rango avisa mientras se escribe y se ajusta al salir del campo', async () => {
    const user = userEvent.setup()
    const onCambio = vi.fn()
    render(<Formulario modulo={pedestal} valores={valoresBase} onCambio={onCambio} />)

    const b = screen.getByLabelText('Ancho sección b (cm)')
    await user.clear(b)
    await user.type(b, '999')
    expect(screen.getByRole('alert')).toHaveTextContent(/fuera de rango/i)
    // Ningún valor emitido sale del rango (99 es válido mientras se escribe "999").
    for (const [nuevos] of onCambio.mock.calls) expect(nuevos.b as number).toBeLessThanOrEqual(200)

    await user.tab()
    expect(onCambio).toHaveBeenLastCalledWith(expect.objectContaining({ b: 200 }))
  })

  it('un campo numérico vacío (no finito) se ignora y revierte al salir', async () => {
    const user = userEvent.setup()
    const onCambio = vi.fn()
    render(<Formulario modulo={pedestal} valores={valoresBase} onCambio={onCambio} />)

    const b = screen.getByLabelText('Ancho sección b (cm)')
    await user.clear(b)
    await user.tab()

    expect(onCambio).not.toHaveBeenCalled()
    expect(b).toHaveValue(30)
  })
})
