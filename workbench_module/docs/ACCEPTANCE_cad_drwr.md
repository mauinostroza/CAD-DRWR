
## CAD-DRWR — validación en Windows (ZWCAD/AutoCAD y SAP2000 reales)

Estas pruebas NO se pueden ejecutar en CI (COM simulado en `tests/test_cad_drwr_bridge*.py`). Hay que hacerlas con el puente recompilado (`build-bridge.yml`) y **vuelto a emparejar**.

1. Abre ZWCAD (o AutoCAD) con un dibujo vacío y el puente. En el módulo «CAD-DRWR» pulsa **Enviar a CAD**: el diálogo debe mostrar programa y documento.
2. **Sin clic**: desmarca «Ubicar con clic» y envía la placa base. Comprueba capas, cotas nativas (editables), textos, tablas y que las entidades omitidas (si hay) se listan con motivo.
3. **Con clic**: marca «Ubicar con clic». Debe aparecer «Haga clic en la ventana de ZWCAD/AutoCAD…» y la ventana del CAD pasar al frente. Haz clic: el dibujo debe quedar con su origen en ese punto. Repite cancelando con Esc: el mensaje debe mostrar el error real y ofrecer «Reintentar» y «Enviar sin ubicar».
4. Repite el paso 3 con el navegador maximizado y con otra ventana encima del CAD (el foco forzado con `AttachThreadInput` es lo que más depende de la versión de Windows). Anota si aparece `RPC_E_SERVERFAULT` (-2147417851).
5. Envía los 7 módulos y revisa visualmente contra la vista previa web y contra los DXF exportados.
6. **SAP2000**: abre un modelo con un grupo que contenga nodos y shells de fundaciones (y columnas apoyadas). En «Fundación SAP2000» pulsa «Leer grupos» y luego «Leer fundación»: debe mostrar progreso y cancelarse. Verifica con el modelo: número de fundaciones (shells adyacentes = una fundación), contorno único con solo las esquinas, espesores, y pedestales con su dimensión real (incluida una columna apoyada en un nodo INTERIOR de la malla).
7. Modelo grande: comprueba que la lectura supera los 30 s del actor sin perder el resultado (el trabajo sigue en segundo plano y el estado pasa a «listo»).
8. Cancela una lectura a mitad y comprueba que las unidades de SAP2000 se restauran (el original las fuerza a N-mm-°C durante la lectura).

Pendiente de verificar en real: formas de retorno de `GetNameList`, `GetAssignments`, `GetPoints`, `GetLocalAxes`, `GetShell`, `GetRectangle`, `GetCoordCartesian`; conteo anidado de `CoInitialize`/`CoUninitialize`; comando `getpoint` con `USERR1..3`; formato `VARIANT` de `AddLightWeightPolyline`, `AddDimRotated` y `AddHatch`; estilo `txt.shx` y grosores de capa; que un `pick` que supera su `timeout_s` mantiene bloqueado el hilo COM hasta que el usuario pulse Esc (las demás llamadas CAD esperan en cola).
