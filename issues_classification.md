# Issues y propuestas — clasificación de ejercicios (Química)

Revisión del repo en el commit `ca9a92f` («Refactored and simplified exercise type classification»).
Los fallos marcados con ✅ ya están corregidos en ese commit; el resto sigue abierto.
Los marcados con 🧪 se han reproducido ejecutando el código.

## Prioridad alta — afectan al resultado de la clasificación

### 1. Corte de año del modelo nuevo inconsistente (2024 vs 2025)
- `guides/extract_text_explicacion.md` dice que 2020–2024 es el modelo de BLOQUES (`A1.`, `B3.`, `C4.`) y que el modelo `PREGUNTA 1–5` / `1A`, `1B` empieza en **2025**.
- `classify_exercise` (notebook 05), la celda que calcula `year_period` y `tipos_ejercicio.json` (`modelo_2020_2023`, `modelo_2024+`) usan **2024** como corte.
- El docstring de `split_exercises` dice «2020 - 2024: year_period = 1» y «2025 - : year_period = 2», pero el comentario del final dice «in exams from 2024».
- **Consecuencia:** los exámenes de 2024 se procesan con el patrón y el diccionario del modelo nuevo.
- **Propuesta:** comprobar con un PDF de 2024 qué modelo tiene, y centralizar el corte en una única función, p. ej. en `extract.py`:
  ```python
  def get_year_period(year: int) -> int:
      if year < 2020:
          return 0
      elif year < 2025:   # ajustar tras comprobar 2024
          return 1
      return 2
  ```
  y usarla tanto en `split_exercises` como en `classify_exercise` (renombrando las claves del JSON en consecuencia).

### 2. Los ejercicios de formulación devuelven un diccionario como `exercise_types` 🧪
- El parámetro de la función se llama `exercise_types` (por defecto `tipos_ejercicio`). En la rama de formulación se asigna `exercise_type` (singular), no `exercise_types`, así que se devuelve el argumento: el **diccionario completo** `tipos_ejercicio`.
- Después `df.explode("exercise_type")` lo convierte en filas basura.
- **Propuesta:** quitar ese parámetro (la función usa `tipos_ejercicio` global de todas formas en `tipos_dict = tipos_ejercicio[exam_model]`) y en formulación hacer `exercise_types = ["Formulación"]` / `["Formulación orgánica"]`. Mejor aún: pasar los diccionarios como parámetros sin valor por defecto y usarlos dentro:
  ```python
  def classify_exercise(exam_name, statement, exercise_types_dict, keywords):
      tipos_dict = exercise_types_dict[exam_model]
  ```

### 3. `UnboundLocalError` si no se reconoce el número de ejercicio 🧪
- Si `re.match(exam_number_pattern, statement)` falla, `exercise_topic` y `exercise_types` nunca se definen y el `return` revienta.
- Pasa siempre con la pregunta 5 del modelo nuevo: `split_exercises` la renombra a `"PREGUNTA 5.-"` y el patrón `^\d{1}?[AB]` no la reconoce.
- **Propuesta:**
  - Inicializar al principio de la función: `exercise_topic, exercise_types = "", []`.
  - Ajustar el patrón del modelo nuevo para reconocer la 5: `r"^(\d[AB]|PREGUNTA 5)"` (y mapearla a la clave `"5"`), o que `split_exercises` la renombre a `"5."` directamente.

### 4. ✅ Tipos de ejercicio sacados del tema equivocado
- Se usaba `keywords[topic]` (variable del bucle) en vez de `keywords[exercise_topic]`. Corregido en `2a8e032`, con la comprobación `if exercise_topic:`.

## Prioridad media — robustez de la clasificación

### 5. Búsqueda de keywords sensible a mayúsculas y por subcadena
- `kw in statement` no encuentra «Equilibrio» si la keyword es «equilibrio». 🧪 (`"3.- El Equilibrio"` sale sin tema.)
- Por subcadena, keywords cortas dan falsos positivos: `"base"` encaja en «basado», «basándose»…
- **Propuesta:** normalizar a minúsculas los dos lados (`statement.lower()`, `kw.lower()`), con cuidado con los símbolos que dependen de mayúsculas (`pH`, `Kc`, `Kp`), y usar límites de palabra para las keywords cortas:
  ```python
  re.search(rf"\b{re.escape(kw)}\b", statement, flags=re.IGNORECASE)
  ```

### 6. Gana el primer tema que encaja
- Un enunciado de equilibrio que mencione «ácido» queda clasificado según el orden de los temas en el JSON.
- **Propuesta:** puntuar cada tema por número de keywords que encajan y quedarse con el máximo:
  ```python
  scores = {t: sum(kw in statement for kw in keywords[t]["keywords_tema"])
            for t in exercise_topic_options}
  best = max(scores, key=scores.get)
  exercise_topic = best if scores[best] > 0 else ""
  ```

### 7. Código muerto / variables sin usar en `classify_exercise`
- `exam_number_key = exercise_number[0]` (typo de `exercise_number_key`) no se usa.
- `exercise_type` (singular) en la rama de formulación no se devuelve (ver #2).
- La variable del bucle de tipos (`exercise_type_keywords`) tiene el mismo nombre que el diccionario que se recorre; funciona, pero confunde. Propuesta: `type_keywords`.

### 8. ✅ Orden de celdas del notebook 05
- La carga de los JSON ya está antes del `def`, y el bucle de 2013 usa `file` en vez de `file_junio_2013`. La celda 7 (que usaba `file_junio_2023`, inexistente) está comentada.
- **Propuesta:** mover `classify_exercise` a `notebooks/scripts/classify.py`, igual que `extract.py`, para evitar dependencias del orden de ejecución.

## Extracción de texto (`notebooks/scripts/extract.py`)

### 9. `year` sin definir si el nombre no contiene año
- En `extract_exercises_from_pdf`, si `re.search(r"\d{4}", file.stem)` no encuentra nada, `year` no existe y falla después.
- **Propuesta:** lanzar un error explícito: `raise ValueError(f"No se encuentra el año en {file.name}")`.

### 10. Código duplicado entre el notebook 03 y `extract.py`
- El notebook 03 contiene una copia completa de las funciones de `extract.py`. Cualquier arreglo hay que hacerlo dos veces.
- **Propuesta:** que el notebook 03 haga `from scripts import extract as ext`, como el 05.

### 11. `start_string` del modelo 2020–2024 no contempla el bloque C
- `start_string = r"[AB]\d{1}\."` solo se usa para recortar el inicio de cada página; si una página empieza por un ejercicio `C`, no se recorta el texto previo (instrucciones del bloque). Revisar si hace falta `[ABC]`.

## Recorte de ejercicios (notebook 04)

### 12. `destination_folder` sin definir si se pasa un `Path`
- En `crop_exercises` y `crop_exercises_from_exam`:
  ```python
  if not isinstance(output_folder, Path):
      destination_folder = Path(output_folder)
  ```
  Si `output_folder` ya es un `Path`, `destination_folder` no existe → `NameError`.
- **Propuesta:** `destination_folder = Path(output_folder)` sin `if` (`Path(Path(...))` es válido).
- Además, el `mkdir` está dentro del bucle de `crop_exercises`; basta con hacerlo una vez fuera.

### 13. `get_exercise_box` pierde ejercicios
- Guarda las palabras en un diccionario cuya clave es el texto (`"1.-"`): si el mismo número aparece dos veces en una página (opciones A y B en la misma hoja), solo queda la última.
- `for page_index in range(2)` fija 2 páginas: un PDF de 1 página da `KeyError` y uno de 3 pierde la tercera.
- Solo reconoce el formato `\d.-` (2010–2019).
- **Propuesta:** recorrer las palabras como lista (no diccionario), iterar sobre `range(len(pdf.pages))` y elegir el patrón según el `year_period`.

## App (`app/selector_examen.py`)

### 14. No funcionará fuera del Mac
- `ROOT = Path("~/code/selector_examenes")` fijo; en el VPS la ruta será otra. Propuesta: `ROOT = Path(__file__).resolve().parents[1]`.
- Los años se buscan con `ROOT / "examenes_quimica"`, pero la carpeta del examen se construye con una ruta relativa (`Path(f"examenes_quimica/...")`), que depende del directorio desde donde se lance Streamlit. Usar `ROOT` en ambos.
- Los años salen sin ordenar: `sorted(years)`.
- Los PDF están en `.gitignore` (`*.pdf`, `*_quimica*`), así que no llegan al servidor con `git pull`. Decidir cómo se suben (rsync, release, almacenamiento aparte).
- `get_available_pdf` devuelve nombres transformados (`replace("_", " ").upper()`) que luego no se pueden usar para abrir el archivo; conviene devolver el `Path` y mostrar el nombre bonito con `format_func` del `selectbox`.

## Diccionarios y organización

### 15. Archivos duplicados que no coinciden
- `diccionarios_clasificacion_ejercicios/temas_por_asignatura.txt` y `…/quimica/temas_por_asignatura.txt` son distintos.
- `diccionarios_clasificacion_ejercicios/tipos_ejercicio.md` y `…/quimica/tipos_ejercicio.md` son distintos.
- `matrices_claude.md` está en la raíz y `mates_II/matrices.md` en su carpeta.
- **Propuesta:** dejar una sola copia de cada uno dentro de su asignatura.

### 16. Temas repetidos con y sin tilde
- En `temas_por_asignatura.txt`: `programacion_lineal` / `programación_lineal`, `distribucion_binomial` / `distribución_binomial`, `contraste_hipotesis` / `contraste_hipótesis`, `inferencia_estadistica` / `inferencia_estadística`…
- **Propuesta:** identificadores sin tildes (más seguros como claves y nombres de archivo) y el nombre con tildes solo para mostrar.

### 17. Ruta `ROOT` fija en todos los notebooks
- `Path("~/code/selector_examenes")` repetido en cada notebook. Propuesta: definirla una vez (p. ej. en `scripts/config.py`) o calcularla relativa al notebook.

## Datos pendientes (anotados en el notebook 02)
- 2012: opciones A y B en PDF separados y además un PDF con ambas → requiere tratamiento manual.
- 2015: renombrar `1.pdf` a `2.pdf` antes del paso 12 del renombrado.
- 2016: solo 5 archivos, falta un examen.
