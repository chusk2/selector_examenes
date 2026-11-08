# Cómo funciona `extract_text.ipynb`

El notebook lee un examen de Química de la PAU/PEvAU de Andalucía en PDF y lo
**divide en preguntas**. El resultado es una lista de diccionarios, uno por pregunta:

```python
[
    {"section": "A", "number": 1, "text": "1.- Formule o nombre los siguientes compuestos: ..."},
    {"section": "A", "number": 2, "text": "2.- a) Justifique cuál de las siguientes especies..."},
    ...
    {"section": "B", "number": 6, "text": "6.- ..."},
]
```

Esto se hace en dos pasos:

1. **`extract_page_text(page)`**: pasa cada página del PDF a texto y convierte los
   subíndices y superíndices de las fórmulas a caracteres Unicode (`H2SO4` → `H₂SO₄`).
2. **`split_questions_from_file(path)`**: une el texto de todas las páginas, lo recorre
   línea a línea y lo reparte en preguntas. Por el camino descarta las cabeceras y las
   instrucciones.

---

## 1. Los formatos de examen que hay que reconocer

Revisando los PDFs de `examenes_quimica/` (2010–2026) aparecen tres formatos:

| Años | Cómo se agrupan las preguntas | Cómo empieza una pregunta | Preguntas por PDF |
|---|---|---|---|
| 2010–2019 | `OPCIÓN A` / `OPCIÓN B` (se elige una) | `1.-`, `2.-` … `6.-` | 12 (6 por opción)* |
| 2020–2024 | `BLOQUE A` / `BLOQUE B` / `BLOQUE C` | `A1.`, `B3.`, `C4.` | 12 |
| 2025–2026 | No hay agrupación | `PREGUNTA 1.-` … `PREGUNTA 5.-` (dentro, las alternativas `1A.` y `1B.`) | 5 |

\* En 2012 algunos ficheros traen una sola opción, así que tienen 6 preguntas.

Hay cosas que se repiten en todos los formatos y que no forman parte de ninguna pregunta:

- **La cabecera**, que aparece **en cada página**. Siempre empieza por
  `UNIVERSIDADES DE ANDALUCÍA` o `PRUEBA DE ACCESO…` / `PRUEBA DE EVALUACIÓN…` y termina
  en la línea que contiene `CURSO 20XX-20XX`.
- **Las instrucciones** (`Instrucciones: a) Duración… g) …`). En los exámenes
  antiguos también se repiten en cada página.
- Textos de relleno antes de la primera pregunta: las `CONSTANTES` en 2025–2026 y la
  explicación de cada bloque en 2020–2024 (`Puntuación máxima…`, `En este bloque…`).

---

## 2. Celda a celda

### Imports

```python
import pdfplumber
from pathlib import Path
from pdfplumber.utils import extract_text
import re
```

- `pdfplumber`: abre el PDF y da acceso a cada carácter con su posición, tamaño y fuente.
- `extract_text` (de `pdfplumber.utils`): a partir de una lista de caracteres, forma
  líneas de texto. Se usa en lugar de `page.extract_text()` porque antes queremos
  modificar algunos caracteres.
- `Path`: para manejar rutas de ficheros.
- `re`: expresiones regulares, para reconocer patrones como `OPCIÓN A` o `3.-`.

### Rutas

```python
ROOT = Path("~/code/selector_examenes").expanduser()
file = ROOT / "examenes_quimica/2017_quimica/2017 - quimica - titular septiembre 6.pdf"
```

`expanduser()` cambia `~` por la carpeta del usuario (`/Users/daniel`). El operador `/`
de `Path` une trozos de ruta.

### Tablas de traducción para sub y superíndices

```python
SUBSCRIPT = str.maketrans("0123456789+-–‒−", "₀₁₂₃₄₅₆₇₈₉₊₋₋₋₋")
SUPERSCRIPT = str.maketrans("0123456789+-–‒−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻⁻")
```

`str.maketrans(a, b)` crea una tabla que cambia cada carácter de `a` por el que ocupa la
misma posición en `b`. Después, `"2".translate(SUBSCRIPT)` devuelve `"₂"`. Los caracteres
que no están en la tabla (por ejemplo, letras) se quedan igual.

En la tabla hay cuatro guiones distintos (`-`, `–`, `‒`, `−`) porque cada PDF usa uno
para el signo menos (`mol⁻¹`, `Cl⁻`), y todos deben convertirse en `⁻` o `₋`.

### Sub y superíndices: `left_neighbor` y `extract_page_text`

**El problema:** en el PDF, el `2` de `H₂O` es un `2` normal escrito con una letra más
pequeña y un poco más abajo. Si se extrae el texto sin más, sale `H2O` o, peor, el `2`
acaba en otra línea:

```
e) H AsO ; f) CH CH CH NH .
3 4 3 2 2 2
```

**La idea:** un carácter es un índice si es **más pequeño que el carácter que tiene
pegado a su izquierda**. En `H₃AsO₄`, el `3` es más pequeño que la `H` que lleva
delante, y el `4` más pequeño que la `O`. Ese carácter de la izquierda es su **base**.

No se puede usar un tamaño fijo (por ejemplo, "menos de 8 puntos"). Unos exámenes usan
letra de 12 pt con índices de 8 pt, otros letra de 10 pt con índices de 7 pt, y algunas
tablas están enteras en letra pequeña sin ser índices. Tampoco se puede usar el orden en
que vienen los caracteres en el PDF: en las ecuaciones, los índices se escriben a
veces al final, después de toda la fórmula.

#### `left_neighbor(char, chars_by_x1)`

```python
def left_neighbor(char, chars_by_x1):
    x = round(char["x0"])
    candidates = [other for key in (x - 1, x, x + 1) for other in chars_by_x1.get(key, [])
                  if other is not char
                  and abs(other["x1"] - char["x0"]) < 1.5
                  and other["top"] < char["bottom"] and char["top"] < other["bottom"]]
    return min(candidates, key=lambda other: abs(other["x1"] - char["x0"]), default=None)
```

Devuelve el carácter que está **justo a la izquierda** de `char`, o `None` si no hay
ninguno. Para que cuente, un carácter tiene que cumplir dos condiciones:

- Su borde derecho (`x1`) está a menos de 1,5 puntos del borde izquierdo de `char`
  (`x0`), es decir, están pegados.
- Comparten algo de altura: uno empieza (`top`) antes de que acabe el otro (`bottom`).
  Así no se toma un carácter de la línea de arriba o de abajo que esté casualmente en la
  misma columna.

Si hay varios candidatos, `min(..., key=...)` se queda con el más pegado. `default=None`
hace que devuelva `None` si la lista está vacía.

`chars_by_x1` es un diccionario que agrupa los caracteres según su borde derecho
redondeado: `{273: [N], 281: [H], ...}`. Con él solo hay que mirar las claves `x-1`, `x`
y `x+1` en lugar de recorrer los ~3000 caracteres de la página para cada carácter. Sin
este índice, la función sería unas mil veces más lenta.

#### `extract_page_text(page)`

```python
def extract_page_text(page):
    chars_by_x1 = {}
    for char in page.chars:
        chars_by_x1.setdefault(round(char["x1"]), []).append(char)

    base_of = {}
    characters = []
    for char in sorted(page.chars, key=lambda char: char["x0"]):
        left = left_neighbor(char, chars_by_x1)
        base = base_of.get(id(left), left)
        if base is not None and char["size"] < 0.9 * base["size"]:
            table = SUPERSCRIPT if char["bottom"] < base["bottom"] - 2 else SUBSCRIPT
            base_of[id(char)] = base
            char = dict(char, text=char["text"].translate(table), top=base["top"], bottom=base["bottom"])
        characters.append(char)
    return extract_text(characters, y_tolerance=4)
```

**Qué hace:** devuelve el texto de una página, con los índices de las fórmulas
convertidos en caracteres Unicode de sub o superíndice.

**Paso a paso:**

1. `page.chars` es la lista de todos los caracteres de la página. Cada uno es un
   diccionario con su texto, su tamaño (`size`) y su posición (`x0`, `x1`, `top`,
   `bottom`…). Las claves están descritas en el propio notebook.
2. Se construye el índice `chars_by_x1`. `setdefault(clave, [])` devuelve la lista de esa
   clave y la crea vacía si todavía no existe.
3. Los caracteres se recorren **de izquierda a derecha** (ordenados por `x0`). Así, cuando
   llega el `¹` de `10⁻¹⁴`, el `⁻` que tiene a su izquierda ya se ha procesado.
4. Para cada carácter:
   - Se busca su vecino izquierdo (`left`).
   - Se decide su **base**. Normalmente es el propio vecino. Pero si el vecino ya es un
     índice (en `10⁻¹⁴`, el vecino del `¹` es el `⁻`), la base es la de ese vecino, el
     `0`. Para eso sirve `base_of`, que apunta cada índice a su base.
     `base_of.get(id(left), left)` devuelve la base guardada o, si no hay ninguna, el
     propio `left`. Se usa `id(...)` como clave porque los diccionarios de pdfplumber no
     pueden ser claves de otro diccionario.
   - Si el carácter mide **menos del 90 %** de su base, es un índice:
     - si su borde inferior queda **más de 2 puntos por encima** del de la base, es un
       **superíndice** (`Na⁺`, `10⁻¹⁴`);
     - si no, es un **subíndice** (`H₂O`).

     `dict(char, text=..., top=..., bottom=...)` crea una copia del carácter con el texto
     traducido y **con la misma altura que su base**. Si no se hace esto, `extract_text`
     podría ponerlo en una línea aparte, porque está unos puntos más abajo o más arriba.
5. Al final, `extract_text(characters, y_tolerance=4)` monta el texto. Junta en la misma
   línea los caracteres cuyo `top` se diferencia en 4 puntos o menos, y dentro de cada
   línea los ordena de izquierda a derecha.

### Expresiones regulares

```python
HEADER_START = re.compile(r"UNIVERSIDADES DE ANDALUC|PRUEBA DE (ACCESO|EVALUACI)")
SECTION = re.compile(r"(?:OPCI[ÓO]N|BLOQUE) ([A-Z])\b")
QUESTION = re.compile(r"(?:PREGUNTA )?(\d+)\s*\.\s*[-–]|([A-Z])(\d+)\.\s")
```

`re.compile` prepara un patrón para usarlo muchas veces. Cada patrón reconoce un tipo de
línea:

- **`HEADER_START`**: primera línea de la cabecera. El `|` significa "o". Se escribe
  `ANDALUC` y `EVALUACI` sin terminar para no depender de las tildes.
- **`SECTION`**: una línea que contiene `OPCIÓN A` o `BLOQUE B`.
  - `(?:...)` agrupa sin guardar lo encontrado.
  - `[ÓO]` acepta la `Ó` con o sin tilde.
  - `([A-Z])` **captura** la letra. Es el grupo 1, y se lee con `match[1]`.
  - `\b` exige que la letra vaya sola. Así, `BLOQUE A (Formulación)` vale, pero una
    palabra como `OPCIÓN AB…` no.
- **`QUESTION`**: el comienzo de una pregunta. Tiene dos alternativas separadas por `|`:
  - `(?:PREGUNTA )?(\d+)\s*\.\s*[-–]` reconoce `1.-`, `PREGUNTA 3.-` y también
    `4. –`, que aparece así en algún PDF.
    - `?` hace que `PREGUNTA ` sea opcional.
    - `(\d+)` captura el número (grupo 1).
    - `\s*` admite espacios opcionales.
    - `[-–]` acepta guion o raya.
  - `([A-Z])(\d+)\.\s` reconoce `A1.`, `B3.`. Captura la letra (grupo 2) y el número
    (grupo 3).

`SECTION` se usa con `.search()`, que busca en cualquier parte de la línea (hay un PDF
en el que sale `c) OPCIÓN A`). `QUESTION` y `HEADER_START` se usan con `.match()`, que
solo mira el **principio** de la línea. Así un `2.-` que aparezca en medio de un
enunciado no se confunde con una pregunta nueva.

### `split_questions_from_file(path)`

```python
def split_questions_from_file(path):
    with pdfplumber.open(path) as pdf:
        text = "\n".join(extract_page_text(page) for page in pdf.pages)

    questions = []
    section = None
    current = None
    in_header = False
    for line in text.splitlines():
        if HEADER_START.match(line):
            in_header = True
        elif in_header:
            in_header = "CURSO" not in line
        elif line.startswith("Instruccion"):
            current = None
        elif match := SECTION.search(line):
            section, current = match[1], None
        elif match := QUESTION.match(line):
            current = {"section": section or match[2],
                       "number": int(match[1] or match[3]),
                       "text": line}
            questions.append(current)
        elif current:
            current["text"] += "\n" + line
    return questions
```

**Qué hace:** abre el PDF, une el texto de todas las páginas y lo recorre **línea a
línea**, decidiendo qué hacer con cada una.

**Variables de estado** (lo que la función "recuerda" mientras avanza):

| Variable | Significado |
|---|---|
| `questions` | Lista final de preguntas. |
| `section` | Letra de la opción o bloque en el que estamos (`"A"`, `"B"`…), o `None` si el examen no tiene. |
| `current` | Pregunta a la que se están añadiendo líneas. Si vale `None`, las líneas se **descartan**. |
| `in_header` | `True` mientras estamos dentro de una cabecera. |

**Qué se hace con cada línea** (se comprueba en este orden y se aplica la primera regla
que se cumple):

1. **Empieza una cabecera** → `in_header = True` y la línea se ignora.
2. **Estamos dentro de la cabecera** → la línea se ignora. Si contiene `CURSO`, es la
   última línea de la cabecera y se pone `in_header = False`.
   La pregunta actual **no** se cierra. Si una pregunta continúa en la página
   siguiente, como la 3B del examen de 2026, sus líneas se siguen añadiendo
   después de la cabecera.
3. **Empiezan las instrucciones** → `current = None`. Desde aquí se descarta todo hasta
   la siguiente pregunta u opción. Así se eliminan las instrucciones y lo que va justo
   después (las `CONSTANTES`).
4. **Línea de `OPCIÓN X` o `BLOQUE X`** → se guarda la letra en `section` y se cierra la
   pregunta (`current = None`). Así, el texto explicativo del bloque
   (`Puntuación máxima…`) no se añade a la pregunta anterior.
5. **Empieza una pregunta** → se crea un diccionario nuevo, se añade a `questions` y pasa
   a ser `current`:
   - `section or match[2]`: la letra de la opción o bloque. En el formato `A1.`, la letra
     viene en la propia pregunta (grupo 2).
   - `int(match[1] or match[3])`: el número. Viene en el grupo 1 (`1.-`) o en el 3
     (`A1.`). Al grupo que no ha coincidido le corresponde `None`, y `or` se queda con
     el otro.
6. **Cualquier otra línea** → si hay una pregunta abierta, es la continuación de su
   enunciado y se le añade. Si no (`current is None`), se descarta.

**Sobre `:=` (operador morsa):** `match := SECTION.search(line)` guarda el resultado en
`match` y a la vez lo usa como condición del `elif`. Si no hay coincidencia, `search`
devuelve `None`, que cuenta como falso.

**Ejemplo:** con un examen de 2017 la función ve estas líneas:

```
UNIVERSIDADES DE ANDALUCÍA          ← regla 1: empieza la cabecera
PRUEBA DE ACCESO Y ADMISIÓN A LA    ← regla 2: dentro de la cabecera
UNIVERSIDAD QUÍMICA                 ← regla 2
CURSO 2016-2017                     ← regla 2: fin de la cabecera
Instrucciones: a) Duración: …       ← regla 3: current = None
b) Elija y desarrolle una opción…   ← regla 6: se descarta (current es None)
OPCIÓN A                            ← regla 4: section = "A"
1.- Formule o nombre los …          ← regla 5: nueva pregunta A1
c) Ácido butanodioico; d) SrO …     ← regla 6: se añade a A1
2.- a) Justifique cuál de …         ← regla 5: nueva pregunta A2
…
UNIVERSIDADES DE ANDALUCÍA          ← cabecera de la página 2
…
OPCIÓN B                            ← regla 4: section = "B"
1.- Formule o nombre …              ← regla 5: nueva pregunta B1
```

### Celdas de prueba

```python
questions = split_questions_from_file(file)
len(questions)                       # 12 para el examen de 2017
for q in questions:
    print(f"[{q['section'] or ''}{q['number']}]", q["text"], sep="\n", end="\n" + "-" * 10 + "\n\n")
```

La última celda imprime cada pregunta con su identificador (`[A1]`, `[B3]`, o solo `[2]`
en los exámenes sin opciones), seguida de una línea separadora.

---

## 3. Resultado sobre todos los PDFs y limitaciones conocidas

Al ejecutar la función sobre los 97 PDFs de `examenes_quimica/`:

- 75 dan 12 preguntas (2 opciones × 6, o bloques A2 + B6 + C4).
- 12 dan 6 preguntas: los ficheros de 2012 que traen una sola opción.
- 10 dan 5 preguntas: los de 2025 y 2026.

Limitaciones:

- **`2019 - quimica - titular junio exámenes a y b.pdf`**: en este PDF el texto
  `OPCIÓN A`/`OPCIÓN B` está superpuesto a otras líneas y sale mezclado
  (`calculadoOraPsC qIuÓeN n Ao sean…`). Las 12 preguntas se separan bien, pero con
  `section = None`, y el enunciado de la pregunta 1 de cada opción sale con letras
  mezcladas.
- **Sub y superíndices:** en todos los PDFs quedan solo 12 líneas formadas únicamente
  por números sueltos (antes eran 377), y la mayoría son números de página. Casos
  que siguen saliendo raros:
  - Notación de isótopos con dos índices apilados a la izquierda (`³⁹₁₉K`): se convierten,
    pero salen intercalados (`₁³₉⁹K`) porque los dos índices ocupan la misma posición
    horizontal.
  - Algún PDF con textos superpuestos (por ejemplo, `2023 - quimica - suplente a.pdf`)
    sigue dando líneas mezcladas, igual que antes.
- Si un año futuro cambia el texto de la cabecera o la forma de numerar las preguntas,
  habrá que añadir la variante a `HEADER_START` o a `QUESTION`.
