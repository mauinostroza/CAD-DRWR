# StructGen CAD

Generador automático de dibujos estructurales en formato **DXF**, compatible
con **AutoCAD** y **ZWCAD**, escrito en **Python + PySide6**.

La aplicación incluye una serie de funciones y formas comunes de ingeniería
estructural —dibujo y acotado de **pernos**, **placas base**, **pedestales**
y su **armadura**, **losas**— además del **armado rápido** de perfiles y
formas de barra, con cuadros de despiece y de pernos generados
automáticamente.

![Interfaz](samples/interfaz.png)

---

## 1. Instalación

Requisitos: **Python 3.9 o superior**.

```bash
pip install -r requirements.txt
python main.py
```

Dependencias:
- `PySide6` — interfaz gráfica.
- `ezdxf` — escritura de archivos DXF (R2010, sin necesidad de CAD abierto).
- `pywin32` — (opcional, Windows) conexión COM en vivo con AutoCAD/ZWCAD.

## 2. Uso general

1. Seleccione un **módulo** en la lista lateral (Placa Base, Pedestal, Losa,
   Perno de Anclaje, Perfil Estructural, Forma de Barra).
2. Edite los **parámetros** del formulario: la vista previa 2D se actualiza
   en vivo.
3. **Exportar DXF…** (`Ctrl+E`) genera el archivo listo para abrir en
   AutoCAD o ZWCAD. **Exportar todo (DXF)** lotea los seis módulos a una
   carpeta.
4. **Guardar/Cargar plantilla** almacena los parámetros del módulo en JSON
   para reutilizar configuraciones típicas.

En la vista previa: **rueda** = zoom, **arrastrar** = paneo,
**doble clic** = ajustar a la ventana.

El encuadre considera la extensión completa de textos, líderes y títulos de
tabla, evitando anotaciones recortadas. Las cotas estrechas desplazan sus
flechas al exterior automáticamente.

### Conexión COM en vivo (AutoCAD / ZWCAD abiertos)

Además del archivo DXF, la aplicación puede **dibujar directamente en el
CAD que esté abierto** en ese momento, sin archivos intermedios:

| Botón | Función |
|-------|---------|
| **Enviar a CAD (COM)** (`Ctrl+G`) | Crea el detalle entidad por entidad en el espacio modelo del documento activo: capas, cotas asociativas nativas, textos, sólidos y polilíneas. Luego regenera y hace zoom extensión. |
| **Abrir DXF en CAD** | Exporta un DXF temporal y lo abre como documento en el CAD activo (útil para conservar el archivo). |
| **Detectar CAD** | Prueba la conexión y muestra programa, versión y documento activo. |
| **Ubicar con clic** (activado por defecto) | Antes de enviar, minimiza la app y el propio CAD pide un clic en pantalla; el dibujo se ubica con su origen en ese punto. Desactive esta opción para enviar siempre en el origen (0,0). |

Requisitos y notas:
- Solo **Windows**, con `pip install pywin32` (incluido en requirements).
- El CAD debe estar **abierto antes de enviar**; la conexión usa
  `GetActiveObject` sobre el ROT de COM.
- Programas soportados: **AutoCAD**, **ZWCAD** (API COM idéntica) y
  **BricsCAD**; en ZWCAD se usa el ProgID `ZWCAD.Application`.
- Si el CAD se ejecuta como administrador, Python debe ejecutarse con el
  mismo nivel de privilegios para que el ROT exponga la sesión.
- Las cotas se crean con `AddDimRotated` (nativas y editables en el CAD);
  las variables `DIMTXT/DIMASZ/DIMEXE/DIMEXO/DIMGAP/DIMTAD…` se ajustan al
  estilo de acotado del módulo.
- La selección del punto se inicia desde el *command loop* nativo del CAD,
  en vez de `Utility.GetPoint` por COM. Esto evita el error
  `RPC_E_SERVERFAULT` que algunas versiones de ZWCAD producen al cambiar el
  foco de ventana.
- Sin pywin32 o sin CAD abierto, la app muestra un aviso claro y todo lo
  demás sigue funcionando (la ruta DXF no depende de COM).

### Escala de acotado

El dibujo se genera a escala 1:1 en milímetros. El parámetro *Escala de
acotado* (1:10 … 1:100) multiplica la altura de textos, cotas y símbolos
con un factor relativo a 1:10. La geometría no cambia; la altura base de
anotación depende del módulo. Comprueba la escala de impresión en CAD.

### Referencias PG y pedestal

En **Pedestal**, selecciona **Referencia 20** para cargar la sección de
550 × 400 mm con 7 barras superiores, 7 inferiores y 3 intermedias en
cada lateral. **Por caras** permite editar esas cantidades. Los lazos
interiores, la elevación y el cuadro de despiece se activan por separado.
Los ganchos cierran en las esquinas, hacia el núcleo; se rechazan radios
que no caben en la geometría solicitada.

El perno **PG** parte del ejemplo de 1 pulgada, hilo 8UN, R=850, P=400,
L=1250 y cantidad 48. El detalle y su tabla usan los mismos parámetros.
Las cotas, tablas y llamadas comparten geometría entre vista previa, DXF
y COM; la apariencia tipográfica puede variar con las fuentes del CAD.

Muestras: [pedestal](samples/pedestal_referencia.png) y
[perno PG](samples/pg_referencia.png), con sus DXF en `samples`.
Se regeneran con `QT_QPA_PLATFORM=offscreen python scripts/render_reference_details.py`.
La comprobación en ZWCAD requiere Windows y una sesión CAD abierta.

## 3. Módulos

| Módulo | Genera |
|--------|--------|
| **Placa Base** | Planta (placa, perforaciones, pernos, ejes) + elevación (columna W, grout, cartelas, soldaduras, N.P.) + detalle del perno + cuadro de pernos. Acotado en dos niveles. Los perfiles W y dimensiones de placa se auto-sugieren. |
| **Pedestal** | Sección con distribución por caras, estribo y lazos interiores con ganchos a 135°, cotas exteriores y recubrimiento; elevación y cuadro de despiece opcionales. |
| **Losa** | Sección transversal con armadura inferior ganchada en apoyos, repartición, armadura superior opcional, hachurado, acotado y despiece. |
| **Perno de Anclaje** | Detalle de perno tipo L (codo 90°), J (gancho 135°) o recto con placa de anclaje: rosca, tuerca, arandela, concreto, N.P. y cuadro de pernos. |
| **Perfil Estructural** | Secciones I/W, H (HEA), canal C, ángulo L, T y caja HSS con acotado completo, ejes y propiedades aproximadas (área y peso lineal). Series comerciales W/HE precargadas. |
| **Forma de Barra** | Barras recta, L 90°, U, estribo cerrado 135° y Z, con radios de doblez reales (R = k·Ø), desarrollo calculado y fila de despiece. |
| **Fundación SAP2000** | Plantas en su posición real (leídas de un modelo SAP2000 abierto), contorno único por fundación, pedestales reales y dos elevaciones (corte real X/Y) por fundación, automáticas y sin traslape. Ver sección 8. |

Las elevaciones altas de pedestales se presentan con una rotura gráfica
convencional: la geometría se mantiene legible y la cota indica siempre la
altura real.

## 4. Lo que se genera en el DXF

- **Capas normalizadas** con colores y grosores: `EJE` (rojo, CENTER),
  `CONCRETO`, `ACERO` (amarillo, grueso), `ACOTADO` (verde), `TEXTOS`
  (cian), `PERFORACIONES` (azul), `SOLDADURA`, `HACHURADO`, `TABLAS`,
  `OCULTO` (HIDDEN).
- **Cotas asociativas nativas** (entidades `DIMENSION`) con estilo
  paramétrico: se pueden editar desde el CAD.
- **Texto** en estilo SHX estándar (`txt.shx`), disponible en AutoCAD y
  ZWCAD.
- **Cuadros de despiece** con marca, forma (boceto), diámetro, cantidad,
  largo de desarrollo, peso unitario (d²/162) y peso total.
- Unidades del documento: milímetros (`$INSUNITS = 4`).

### Ejemplos generados

| | |
|---|---|
| ![Placa base](samples/placa_base.png) | ![Pedestal](samples/pedestal.png) |
| ![Losa](samples/losa.png) | ![Perno](samples/perno_anclaje.png) |

Los archivos `samples/*.dxf` son salidas de ejemplo de cada módulo; ábralos
directamente en AutoCAD o ZWCAD para verificar.

## 5. Arquitectura del código

```
StructGenCAD/
├── main.py                  Punto de entrada
├── core/
│   ├── ir.py                Representación intermedia (entidades del dibujo)
│   ├── geom.py              Hachurado, barras dobladas (poly_bar), símbolos
│   ├── dims.py              Acotado con niveles (cadenas + totales)
│   └── tables.py            Cuadros de despiece y de pernos
├── cad/
│   ├── dxf_out.py           IR -> DXF R2010 (ezdxf)
│   └── com_live.py          IR -> sesión CAD abierta (COM/ActiveX en vivo)
├── generators/
│   ├── data.py              Bases de datos de perfiles, diámetros, escalas
│   ├── panels.py            Formularios declarativos (SPEC) de PySide6
│   ├── base_plate.py        Placa base
│   ├── pedestal.py          Pedestal
│   ├── slab.py              Losa
│   ├── anchor_bolt.py       Perno de anclaje
│   ├── profile.py           Perfiles estructurales
│   └── bar_shape.py         Formas de barra
├── app/
│   ├── main_window.py       Ventana principal
│   └── preview.py           Vista previa 2D (QPainter, zoom/pan)
└── samples/                 DXF y PNG de ejemplo de cada módulo
```

Punto clave del diseño: la **vista previa, el DXF y la conexión COM en vivo
consumen la misma representación intermedia**. Cada generador construye un
`Drawing` (líneas, arcos, polilíneas, cotas, tablas, líderes) que el visor
pinta con QPainter, `cad/dxf_out.py` traduce a entidades DXF y
`cad/com_live.py` recrea entidad por entidad en el CAD abierto vía COM —
lo que ve es exactamente lo que se exporta.

Para **agregar un módulo nuevo**: cree un archivo en `generators/` con una
clase `SpecPanel` (SPEC declarativo) y una función `builder(params) ->
Drawing`, y regístrelo en `generators/__init__.py`.

## 6. Notas de cálculo incluidas

- Peso de barra corrugada: `d²/162` kg/m.
- Desarrollo de barras dobladas: suma de tramos rectos + arcos al radio de
  línea central (R interior + Ø/2).
- Ganchos de estribo a 135° con largo `6Ø ≥ 75 mm`; radios de doblez de
  barra `k·Ø` (k configurable, 4 por defecto).
- Perforaciones de placa sobredimensionadas `Ø + 6 mm`.
- Propiedades de perfiles sin radios de unión (aproximadas).

## 7. Generar ejecutable (.exe)

El repositorio incluye un workflow de GitHub Actions
(`.github/workflows/build-exe.yml`) que compila un `.exe` de Windows con
PyInstaller. Es de disparo **manual**:

1. En GitHub, ir a la pestaña **Actions** → **Build Windows EXE**.
2. Click en **Run workflow** (opcionalmente indicar una etiqueta de
   versión).
3. Al finalizar, descargar el artefacto `StructGenCAD-windows-exe` desde
   la ejecución del workflow.

Para compilarlo localmente en Windows:

```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name StructGenCAD main.py
```

El ejecutable queda en `dist/StructGenCAD.exe`.

## 8. Módulo "Fundación SAP2000"

Lee la geometría de fundaciones ya modeladas en **SAP2000** (nodos y
shells de área) para dibujarlas automáticamente:

1. En SAP2000, agrupe los shells (y opcionalmente nodos) de sus
   fundaciones en un **grupo** (Assign > Group Names). Un mismo grupo
   puede contener **más de una fundación física** (varios shells sin
   relación entre sí, p. ej. todas las zapatas de una zona): StructGenCAD
   separa automáticamente el grupo en fundaciones independientes por
   adyacencia de shells (dos shells pertenecen a la misma fundación si
   comparten una arista).
2. En StructGenCAD, seleccione el módulo **Fundación SAP2000** y presione
   **Conectar a SAP2000** (SAP2000 debe estar abierto con el modelo
   cargado; usa la misma conexión COM/OAPI que ZWCAD/AutoCAD, pero es una
   conexión independiente — puede tener SAP2000 y el CAD abiertos a la
   vez).
3. Elija el grupo en la lista. Por cada fundación detectada dentro del
   grupo se dibuja:
   - **Planta**: una única polilínea cerrada con el contorno exterior real
     (solo esquinas — para una fundación rectangular, 4 vértices; se
     agregan más solo si hay lados no colineales), acotada alrededor de
     esa fundación, usando el espesor de la propiedad de área asignada
     (auto-detectado; **siempre editable**, por si la versión de SAP2000
     no expone el espesor con la firma esperada).
   - **Pedestal(es)**: si hay una columna (frame vertical) apoyada sobre
     la fundación —incluso en un nodo interior de la malla, no solo en
     sus esquinas—, se dibuja con su dimensión real (rectangular o
     circular, leída de la sección del frame) en su posición exacta.
   - **Dos elevaciones individuales** por fundación, "sus dos lados":
     corte real de la geometría (no un simple bounding-box) perpendicular
     a X y perpendicular a Y, pasando automáticamente por el pedestal de
     esa fundación o, si no tiene, por su centroide. En fundaciones
     combinadas o con espesor escalonado, el corte puede generar más de
     un tramo. Cada elevación queda rotulada ("NOMBRE — CORTE EJE X/Y")
     y dibujada de forma aislada, como si esa fundación estuviera sola en
     el espacio: solo se cortan sus propios shells, nada de otras
     fundaciones se interpone.
   - Las plantas se dibujan en su **posición real** dentro del modelo
     (misma disposición relativa que en SAP2000, sin recolocarlas); las
     elevaciones se dibujan en una fila aparte, bien alejada de las
     plantas, con las dos elevaciones de cada fundación juntas y un
     espacio mayor entre los pares de fundaciones distintas, sin
     traslaparse entre sí.
4. Exporte a DXF o envíe a ZWCAD/AutoCAD igual que cualquier otro módulo.

Supuesto de dibujo: la cota Z de los joints del shell se toma como el
**tope** de la fundación; la elevación se extruye hacia abajo el espesor
leído/editado.

## 9. Extensiones posibles

- Plantillas de cajetín (rúbrica) y marco.
- Más perfiles (HP, cañas, angulares dobles), placas de espera y conexiones
  empernadas/soldadas.
- Exportación directa a DWG mediante ODA File Converter.

## 9. Pruebas

Las pruebas comprueban la generación de todos los módulos, unidades de los
rótulos de armadura, encuadre de anotaciones, tablas, cotas estrechas y
representación abreviada de pedestales altos:

```bash
python -m unittest discover -s tests -v
```

También se ejecutan automáticamente en cada pull request mediante GitHub
Actions.
