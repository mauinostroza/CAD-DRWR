
## CAD-DRWR (StructGenCAD) — detalles estructurales 2D

Módulo `cad_drwr`: dibuja detalles estructurales (placa base, pedestal, losa, perno de anclaje, perfil, forma de barra y fundaciones leídas de SAP2000), los exporta a DXF/SVG/PNG y los envía a ZWCAD/AutoCAD mediante el puente local.

| Destino | Fuente | Commit |
|---|---|---|
| `backend/motor_calculo/cad_drwr/core/*.py` | `mauinostroza/CAD-DRWR` `core/*.py` | `{COMMIT}` |
| `backend/motor_calculo/cad_drwr/dxf_out.py` | `cad/dxf_out.py` | `{COMMIT}` |
| `backend/motor_calculo/cad_drwr/generators/*.py` | `generators/*.py` (sin clases Qt; `SPEC` y `autollenar` como datos/funciones puras) | `{COMMIT}` |
| `backend/motor_calculo/cad_drwr/sap_geom.py` | `cad/sap2000_link.py` (solo dataclasses `Pedestal`, `AreaGeom`, `Zapata`, `FundacionGeom`) | `{COMMIT}` |
| `bridge/cad_com_live.py` | `cad/com_live.py` | `{COMMIT}` |
| `bridge/cad_sap_link.py` | `cad/sap2000_link.py` (+ `ModelLink`, `ControlTrabajo`) | `{COMMIT}` |

Código nuevo (no copiado): `serializar.py`, `servicio.py`, `volcado.py`, `generators/__init__.py` (registro), `generators/reglas_ui.py`, `backend/routers/cad_drwr.py`, `bridge/cad_drwr.py`, `bridge/cad_drwr_sap.py` y todo `web/src/cad_drwr/`.

### Paridad
- `scripts/check_engine_parity.py` (repo de origen) compara por AST `core/`, `dxf_out.py` y `generators/data.py`: 0 diferencias de lógica (solo imports relativos y docstrings).
- `golden/*.json` se generó con el escritorio original (Qt fuera de pantalla) y las pruebas `test_cad_drwr_*_golden.py` exigen que el motor copiado reproduzca el mismo dibujo (IR volcada) para los 7 módulos, incluidos defaults reales de la interfaz y variantes.
- `golden/reglas_ui.json` (59 escenarios) fija el autollenado y los campos habilitados del escritorio; `web/src/cad_drwr/reglas.test.ts` exige que el porte a TypeScript coincida.

### Desviaciones honestas respecto del escritorio
- Los `build_*` se copian tal cual; las inconsistencias del original NO se corrigieron: texto «GROUT: MORTERO DE PEGADO e = 20 MPa» (placa base), fallbacks distintos de `r_zapata` en el pedestal (`_starter_path` frente a `_validate_starters`), `esp if esp else espesor_default` redundante en la elevación de fundaciones, y en perfil «Ángulo L»/«Caja HSS» ignoran `tf`.
- Con una serie comercial seleccionada, editar `d`, `bf`, `tw` o `tf` en el perfil se revierte de inmediato al valor de la serie (comportamiento del original).
- El módulo «Fundación SAP2000» no tiene formulario declarativo: sus parámetros son `escala`, `espesor_default` y la geometría `_geom`, que se lee con el puente.
- La vista previa web es SVG (no QPainter): el aplanado de cotas, llamadas y tablas usa las mismas funciones que DXF y COM (`core/annotations.py`, `core/dims.py`).
- El puente CAD copia `cad/com_live.py` sin ezdxf: `_infer_th`/`_infer_ltscale` se reemplazan por `serializar.inferir_th`; `_tabla_prims` se elimina (las tablas llegan aplanadas).
- `TrabajoCancelado` hereda de `BaseException` para que los `except Exception` tolerantes de `sap2000_link` no se traguen la cancelación.
- Las lecturas COM de `cad_sap_link.py` (`coordenada`, `orientacion_frame`) usan `bridge.actions.split_return` del workbench: el código de retorno puede ir al inicio (pywin32) o al final (comtypes). El resto de parsers del original ya eran tolerantes (filtran por tipo). Pruebas con el doble `_RetFirst` en `tests/test_cad_drwr_bridge_sap.py`.
