
## CAD-DRWR: ZWCAD/AutoCAD y lectura de fundaciones

Todas son `POST` bajo `/v1/sap/actions/cad/`. Las del CAD usan un actor COM propio (hilo STA aparte, timeouts largos) y NO necesitan SAP2000 abierto. Las de SAP usan el `call` común del puente (timeout de 30 s del actor: la lectura corre en segundo plano y la web sondea el estado).

| Ruta | Efecto |
|---|---|
| `cad/status` | Detecta AutoCAD/ZWCAD/BricsCAD abierto: `{conectado, programa, version, documento, detalle}` (200 incluso sin CAD). |
| `cad/pick` | Pide un clic de inserción en el CAD (comando nativo, foco forzado con `AttachThreadInput`). `{mensaje?, timeout_s?}` → `{x, y}`. Cancelación o error COM → 409 con el texto real. |
| `cad/draw/begin` | Abre una sesión de dibujo (**exige `confirmed: true`**): crea capas y variables de cota. `{confirmed, origen?, n_total, th}` → `{sesion, programa, documento}`. TTL 10 min. |
| `cad/draw/batch` | Emite hasta 1000 entidades (`line`, `circle`, `arc`, `poly`, `filled`, `text`, `dim`). Valida tipos, números finitos, capas, textos ≤ 500 y polilíneas ≤ 2000 puntos. `{sesion, ents}` → `{creadas, omitidas, errores:[{indice,tipo,motivo}]}`. |
| `cad/draw/end` | Regen + ZoomExtents y libera la sesión. → `{documento, creadas, omitidas, resumen}`. |
| `cad/sap/groups` | Grupos de SAP2000 con shells: `{grupos:[{nombre, n_shells}]}`. |
| `cad/sap/foundation/start` | Inicia la lectura de una fundación (un trabajo a la vez, 409 si hay otro): `{grupo}` → `{job}`. |
| `cad/sap/foundation/status` | `{estado, etapa, hechas, total, transcurrido_s, resultado?, error?}`; `resultado` es `FundacionGeom.to_dict()`. |
| `cad/sap/foundation/cancel` | Cancelación cooperativa (la siguiente operación COM la detecta). |

Reglas heredadas del puente: nunca rutas de archivo en el payload; mutaciones con `confirmed: true`; errores de validación 422 en español; errores COM 409 con el texto real. Las firmas COM no verificadas contra una instancia real quedan marcadas en `SAP2000_ACCEPTANCE.md`.
