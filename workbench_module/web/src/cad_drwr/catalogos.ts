// Generado desde backend/motor_calculo/cad_drwr/generators/data.py (literales idénticos).

export type Tabla = Record<string, { d: number; bf: number; tw: number; tf: number }>

/** Perfiles W (dimensiones nominales en mm), AISC/CISC métrico. */
export const W_DB: Tabla = {
  W150X24: { d: 162, bf: 154, tw: 6.6, tf: 9.1 },
  W200X22: { d: 203, bf: 102, tw: 6.2, tf: 8.4 },
  W250X25: { d: 257, bf: 101, tw: 5.8, tf: 8.4 },
  W310X39: { d: 310, bf: 165, tw: 5.8, tf: 10.2 },
  W360X45: { d: 356, bf: 127, tw: 7.5, tf: 11.9 },
  W410X46: { d: 404, bf: 140, tw: 6.4, tf: 11.6 },
  W530X66: { d: 533, bf: 165, tw: 7.5, tf: 13.5 },
}

/** Perfiles H (HEA aproximado). */
export const HE_DB: Tabla = {
  HE200A: { d: 190, bf: 200, tw: 6.5, tf: 10 },
  HE240A: { d: 230, bf: 240, tw: 7.5, tf: 12 },
  HE300A: { d: 270, bf: 300, tw: 8.5, tf: 14 },
}

/** Diámetros de pernos comunes (mm). */
export const DIAM_PERNOS: number[] = [16, 19, 22, 25, 29, 32]
/** Diámetros de barra corrugada (mm). */
export const DIAM_BARRAS: number[] = [8, 10, 12, 16, 18, 22, 25, 28, 32]
/** Escalas de acotado. */
export const ESCALAS: string[] = ['1:10', '1:20', '1:25', '1:50', '1:75', '1:100']
