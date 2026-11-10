# Claves de `page.chars` en pdfplumber

Cada elemento de `page.chars` es un diccionario con la información de un carácter.
Ejemplo real: la "C" de la cabecera del examen `IMPRESO-QUIMICA-ORD-TITULAR-EXAMEN.pdf`.

```python
{'matrix': (1.0, 0.0, 0.0, 1.0, 241.83, 779.76),
 'fontname': 'BCDEEE+ArialNarrow-Bold',
 'adv': 7.67, 'upright': True,
 'x0': 241.83, 'y0': 777.04, 'x1': 249.50, 'y1': 790.00,
 'width': 7.67, 'height': 12.96, 'size': 12.96,
 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 1,
 'ncs': 'DeviceGray', 'text': 'C',
 'stroking_color': (0.0,), 'non_stroking_color': (0.0,),
 'top': 51.92, 'bottom': 64.88, 'doctop': 51.92}
```

## Identificación

| Clave | Significado |
|---|---|
| `text` | El carácter (`'C'`) |
| `object_type` | Siempre `'char'` |
| `page_number` | Número de página (empieza en 1) |

## Fuente

| Clave | Significado |
|---|---|
| `fontname` | Nombre de la fuente. El prefijo (`BCDEEE+`) es el código del subconjunto incrustado; lo útil va detrás (`ArialNarrow-Bold` → negrita) |
| `size` | Tamaño en puntos. **Clave para detectar sub/superíndices** |
| `adv` | Avance horizontal: cuánto se desplaza el cursor tras el carácter |
| `upright` | `True` si el texto es horizontal; `False` si está girado |

## Posición

Todas las medidas en puntos (1 pt = 1/72 de pulgada).

| Clave | Significado |
|---|---|
| `x0`, `x1` | Borde izquierdo y derecho, medidos desde la izquierda de la página |
| `top`, `bottom` | Borde superior e inferior, medidos **desde arriba** de la página (los cómodos) |
| `y0`, `y1` | Lo mismo, pero medido **desde abajo** (sistema interno del PDF) |
| `doctop` | Como `top`, pero desde el inicio del documento (útil para ordenar entre páginas) |
| `width`, `height` | `x1 − x0` y `bottom − top` |
| `matrix` | Matriz de transformación del PDF: los dos últimos valores son la posición; los cuatro primeros, escala/giro |

## Color

| Clave | Significado |
|---|---|
| `non_stroking_color` | Color de relleno, es decir, el color del texto (`(0.0,)` = negro en gris) |
| `stroking_color` | Color del contorno |
| `ncs` | Espacio de color (`'DeviceGray'`, `'DeviceRGB'`…) |

## Estructura (solo PDF etiquetados para accesibilidad)

| Clave | Significado |
|---|---|
| `tag` | Etiqueta de estructura |
| `mcid` | Identificador del bloque de contenido |

En los exámenes de selectividad ambas valen `None`.

## Lo que necesitas para el clasificador

`text`, `size`, `fontname`, `x0`/`x1` y `top`/`bottom`.
