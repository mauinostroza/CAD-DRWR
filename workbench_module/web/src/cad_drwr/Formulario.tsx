import { useId, useState } from 'react'
import { aplicarCambio, habilitados, soportaModulo } from './reglas'
import type { CampoFloat, CampoInt, ModuloInfo, ParamValor, Params } from './tipos'
import './formulario.css'

export type FormularioProps = {
  modulo: ModuloInfo
  valores: Params
  /** Recibe el Params completo tras el cambio (autollenado y _escala incluidos). */
  onCambio: (nuevos: Params) => void
  deshabilitado?: boolean
}

/** Número finito del texto, o null si está vacío o no es numérico. */
function aNumero(texto: string): number | null {
  if (texto.trim() === '') return null
  const n = Number(texto)
  return Number.isFinite(n) ? n : null
}

function limitar(campo: CampoInt | CampoFloat, n: number): number {
  const acotado = Math.min(campo.max, Math.max(campo.min, n))
  return campo.kind === 'int' ? Math.round(acotado) : acotado
}

type CampoNumeroProps = {
  id: string
  campo: CampoInt | CampoFloat
  valor: number
  off: boolean
  onElegir: (valor: number) => void
}

function CampoNumero({ id, campo, valor, off, onElegir }: CampoNumeroProps) {
  const [borrador, setBorrador] = useState<{ de: number; texto: string } | null>(null)
  const texto = borrador !== null && borrador.de === valor ? borrador.texto : String(valor)
  const numero = aNumero(texto)
  const fuera = numero !== null && (numero < campo.min || numero > campo.max)
  const errorId = `${id}-error`
  const sufijo = campo.suffix.trim()

  return (
    <>
      <label htmlFor={id}>{campo.label}</label>
      <div className="cad-entrada">
        <input
          id={id}
          type="number"
          min={campo.min}
          max={campo.max}
          step={campo.step}
          value={texto}
          disabled={off}
          aria-invalid={fuera || undefined}
          aria-describedby={fuera ? errorId : undefined}
          onChange={e => {
            const t = e.target.value
            setBorrador({ de: valor, texto: t })
            const n = aNumero(t)
            if (n !== null && n >= campo.min && n <= campo.max) {
              onElegir(campo.kind === 'int' ? Math.round(n) : n)
            }
          }}
          onBlur={() => {
            if (numero !== null && fuera) onElegir(limitar(campo, numero))
            setBorrador(null)
          }}
        />
        {sufijo !== '' && <span className="cad-sufijo">{sufijo}</span>}
      </div>
      {fuera && (
        <p id={errorId} className="cad-error" role="alert">
          Valor fuera de rango: debe estar entre {campo.min} y {campo.max}. Se ajustará al salir del campo.
        </p>
      )}
    </>
  )
}

export function Formulario({ modulo, valores, onCambio, deshabilitado = false }: FormularioProps) {
  const prefijo = useId().replace(/[^a-zA-Z0-9_-]/g, '')

  if (modulo.interactivo) {
    return <p className="cad-aviso">El módulo {modulo.nombre} usa su propio panel.</p>
  }

  const conReglas = soportaModulo(modulo.id)
  const reglas: Record<string, boolean> = conReglas ? habilitados(modulo.id, valores) : {}

  const cambiar = (campo: string, valor: ParamValor) => {
    onCambio(
      conReglas ? aplicarCambio(modulo.id, valores, campo, valor, valores) : { ...valores, [campo]: valor },
    )
  }

  return (
    <div className="cad-formulario" role="group" aria-label={`Parámetros de ${modulo.nombre}`}>
      {modulo.campos.map(campo => {
        const id = `${prefijo}-${campo.key}`
        const off = deshabilitado || reglas[campo.key] === false
        const actual = valores[campo.key] ?? campo.value

        if (campo.kind === 'combo') {
          return (
            <FilaCombo
              key={campo.key}
              id={id}
              etiqueta={campo.label}
              opciones={campo.options}
              valor={String(actual)}
              off={off}
              onElegir={v => cambiar(campo.key, v)}
            />
          )
        }
        if (campo.kind === 'chk') {
          return (
            <FilaCheck
              key={campo.key}
              id={id}
              etiqueta={campo.label}
              valor={Boolean(actual)}
              off={off}
              onElegir={v => cambiar(campo.key, v)}
            />
          )
        }
        return (
          <CampoNumero
            key={campo.key}
            id={id}
            campo={campo}
            valor={Number(actual)}
            off={off}
            onElegir={v => cambiar(campo.key, v)}
          />
        )
      })}
    </div>
  )
}

function FilaCombo(props: {
  id: string
  etiqueta: string
  opciones: string[]
  valor: string
  off: boolean
  onElegir: (valor: string) => void
}) {
  const { id, etiqueta, opciones, valor, off, onElegir } = props
  return (
    <>
      <label htmlFor={id}>{etiqueta}</label>
      <select id={id} value={valor} disabled={off} onChange={e => onElegir(e.target.value)}>
        {opciones.map(o => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </>
  )
}

function FilaCheck(props: {
  id: string
  etiqueta: string
  valor: boolean
  off: boolean
  onElegir: (valor: boolean) => void
}) {
  const { id, etiqueta, valor, off, onElegir } = props
  return (
    <>
      <label htmlFor={id}>{etiqueta}</label>
      <input
        id={id}
        type="checkbox"
        checked={valor}
        disabled={off}
        onChange={e => onElegir(e.target.checked)}
      />
    </>
  )
}
