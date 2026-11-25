import pdfplumber
from pathlib import Path
from pdfplumber.utils.text import extract_text
import re
from collections import Counter
import pandas as pd


ROOT = Path("~/code/selector_examenes").expanduser()


# Diccionarios de sustitución de caracteres con `str.maketrans()`

SUBSCRIPT = str.maketrans("0123456789+-–‒−", "₀₁₂₃₄₅₆₇₈₉₊₋₋₋₋")
SUPERSCRIPT = str.maketrans("0123456789+-–‒−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻⁻")


# Caracteres de la fuente Symbol (Δ, [, ], letras griegas, →...)

# La fuente Symbol guarda sus glifos en el área de uso privado de Unicode (U+F020–U+F0FF):
# el código original es el del carácter menos 0xF000 (U+F044 -> 0x44 "D") y la fuente
# dibuja en esa posición su propio glifo (0x44 -> Δ)
_SYMBOL_LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_SYMBOL_GREEK = "ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖαβχδεφγηιϕκλμνοπθρστυϖωξψζ"
SYMBOL_FONT = {ord(latin): greek for latin, greek in zip(_SYMBOL_LATIN, _SYMBOL_GREEK)}
SYMBOL_FONT.update({
    0x2D: "−", 0xA2: "′", 0xA3: "≤", 0xA5: "∞", 0xAB: "↔", 0xAC: "←", 0xAE: "→",
    0xB0: "°", 0xB1: "±", 0xB3: "≥", 0xB4: "×", 0xB7: "•", 0xB8: "÷", 0xB9: "≠",
    0xBB: "≈", 0xD6: "√", 0xD7: "·", 0xDB: "⇔", 0xDE: "⇒",
})


def decode_symbol_font(text, fontname=""):
    """Convierte los caracteres de la fuente Symbol en sus equivalentes Unicode reales.

    - Caracteres del área privada (U+F020–U+F0FF): siempre se convierten.
    - Caracteres normales con fuente Symbol (p. ej. "D" que se dibuja como Δ): se convierten
      si `fontname` contiene "Symbol".
    Los que coinciden con ASCII ([, ], (, ), +, =...) quedan como el carácter ASCII.
    """
    is_symbol_font = "Symbol" in fontname
    decoded = []
    for character in text:
        code = ord(character)
        if 0xF020 <= code <= 0xF0FF:
            code -= 0xF000
        elif not is_symbol_font:
            decoded.append(character)
            continue
        decoded.append(SYMBOL_FONT.get(code, chr(code)))
    return "".join(decoded)


def left_neighbor(char, chars_by_x1):
    """Carácter que termina justo donde empieza `char` (a menos de 1,5 pt) y a su misma altura."""
    x = round(char["x0"])
    candidates = [other for key in (x - 1, x, x + 1) for other in chars_by_x1.get(key, [])
                  if other is not char
                  and abs(other["x1"] - char["x0"]) < 1.5
                  and other["top"] < char["bottom"] and char["top"] < other["bottom"]]
    return min(candidates, key=lambda other: abs(other["x1"] - char["x0"]), default=None)


def reorder_ion_indexes(chars, characters, base_of, kind_of):
    """Coloca el subíndice numérico antes del superíndice cuando ambos acompañan a la
    misma base y se solapan en horizontal. Modifica `characters` (los caracteres ya
    convertidos, en las mismas posiciones que `chars`)."""
    positions_by_base = {}
    for position, char in enumerate(chars):
        if id(char) in base_of:
            positions_by_base.setdefault(id(base_of[id(char)]), []).append(position)

    for positions in positions_by_base.values():
        subs = sorted((p for p in positions if kind_of[id(chars[p])] == "sub"),
                      key=lambda p: characters[p]["x0"])
        sups = sorted((p for p in positions if kind_of[id(chars[p])] == "sup"),
                      key=lambda p: characters[p]["x0"])
        if not subs or not sups or not all(chars[p]["text"].isdigit() for p in subs):
            continue
        # solo si están superpuestos (la carga empieza antes de que acabe el subíndice)
        if characters[sups[0]]["x0"] >= characters[subs[-1]]["x1"]:
            continue
        ordered = subs + sups
        start = min(characters[p]["x0"] for p in ordered)
        end = max(characters[p]["x1"] for p in ordered)
        width = (end - start) / len(ordered)
        # se reparten seguidos en el mismo hueco: sin separación entre ellos (no se añaden
        # espacios) y sin pasar del final del grupo (no se mezclan con lo que va detrás)
        for n, p in enumerate(ordered):
            characters[p] = dict(characters[p], x0=start + n * width, x1=start + (n + 1) * width)



def extract_text_from_page(page):
    """Texto de la página convirtiendo los sub/superíndices en caracteres Unicode."""
    chars = [dict(char, text=decode_symbol_font(char["text"], char["fontname"]))
             for char in page.chars]
    if not chars:
        return ""

    # tamaño del texto normal (el más frecuente): un índice siempre es más pequeño.
    # Evita que todo lo que va detrás de un carácter grande (los corchetes de
    # ΔH°[C₄H₁₀(g)]) se tome como índice
    body_size = Counter(round(char["size"], 1) for char in chars
                        if char["text"].strip()).most_common(1)[0][0]

    # índice de los caracteres por su borde derecho (redondeado) para encontrar vecinos rápido
    chars_by_x1 = {}
    for char in chars:
        chars_by_x1.setdefault(round(char["x1"]), []).append(char)

    # 1) detectar los índices y su tipo
    base_of = {}       # id(índice) -> carácter normal al que acompaña (la "H" de "H₂")
    kind_of = {}       # id(índice) -> "sub" | "sup"
    for char in sorted(chars, key=lambda char: char["x0"]):   # de izquierda a derecha
        left = left_neighbor(char, chars_by_x1)
        # si el vecino ya es un índice (el "¹" de "10⁻¹⁴"), la base es la de ese vecino
        base = base_of.get(id(left), left)
        if (base is not None
                and char["size"] < 0.9 * base["size"]
                and char["size"] < 0.9 * body_size):
            base_of[id(char)] = base
            # superíndice si su base queda claramente por encima de la del carácter normal
            kind_of[id(char)] = "sup" if char["bottom"] < base["bottom"] - 2 else "sub"

    # nº de letras de cada índice: una sola letra (Kc, Kp, H°) se convierte,
    # una palabra (el "combustión" de ΔH°combustión) se deja tal cual
    letters_in_index = Counter((id(base_of[id(char)]), kind_of[id(char)]) for char in chars
                               if id(char) in base_of and char["text"].isalpha())

    # 2) convertir los índices a caracteres Unicode
    characters = []
    for char in chars:
        if id(char) in base_of:
            base, kind = base_of[id(char)], kind_of[id(char)]
            text = char["text"]
            if text.isalpha():
                if letters_in_index[(id(base), kind)] == 1:
                    if kind == "sub":
                        text = text.lower()   # KC -> Kc, KP -> Kp (en texto normal para poder buscarlas)
                    elif text == "o":
                        text = "°"            # estado estándar: ΔH°
            else:
                text = text.translate(SUPERSCRIPT if kind == "sup" else SUBSCRIPT)
            # se le da la altura de su base para que extract_text lo ponga en la misma línea
            char = dict(char, text=text, top=base["top"], bottom=base["bottom"])
        characters.append(char)

    # 3) subíndice y carga de un ion (SO₄²⁻): en el PDF están uno encima del otro,
    # en la misma x, y al ordenar por x0 sale "SO²₄⁻". Se pone primero el subíndice
    # (si es numérico; en ΔH°f se respeta el orden) y después la carga
    reorder_ion_indexes(chars, characters, base_of, kind_of)

    # extract_text junta en una línea los caracteres cuyo top difiere como máximo y_tolerance
    # y dentro de cada línea los ordena por x0
    return extract_text(characters, y_tolerance=4)


def clean_page_text_2020_2024(page_text):
    """Formatea el texto del examen usando el formato de examen de 2020 - 2024"""
    text_lines = page_text.split("\n")
    # obtener índices de líneas a eliminar
    bloque_line_indexes = []
    for index, line in enumerate(text_lines):
        if "BLOQUE" in line:
            bloque_line_indexes.append(index)

    # borrar línea que empieza por BLOQUE y
    # las 3 siguientes (BLOQUE A) o
    # las 4 siguientes (BLOQUE B, C)
    line_indexes_to_remove = []
    # en cada línea que empieza por BLOQUE,
    # se marca esa línea y las 4 (ó 3) siguientes líneas
    for idx in bloque_line_indexes:
        if text_lines[idx].startswith("BLOQUE A"):
            line_indexes_to_remove.extend(list(range(idx, idx+4)))
        else:
            line_indexes_to_remove.extend(list(range(idx, idx+5)))

    # filtrar las líneas para excluir las instrucciones del bloque        
    page_text = "\n".join([text_lines[idx] for idx in range(len(text_lines))
                        if idx not in line_indexes_to_remove])

    # inserta una línea en blanco bajo cada ejercicio
    page_text = re.sub(r"(^[ABC]\d{1}\.)", r"\n\1", page_text, flags=re.MULTILINE)

    return page_text


def extract_exercises_from_pdf(file: Path) -> str:
    match_year = re.search(r"\d{4}", file.stem)
    if match_year:
        year = int(match_year.group(0))

    # inserto cabecera con nombre del archivo
    exam_text = f"{file.stem}\n" + "-" * len(file.stem) + "\n"

    # string donde comienzan los ejercicios
    if year <= 2019:
        start_string = "OPCIÓN"
    else:
        start_string = r"[AB]\d{1}\."

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = extract_text_from_page(page)
            
            match = re.search(start_string, page_text)
            
            # recortar líneas iniciales hasta start_string
            if match:
                page_text = page_text[match.start():]

            # convertir a minúsculas la opción
            page_text = (page_text
                         .replace("OPCIÓN", "Opción")
                         .replace("Opción B", "\n\nOpción B")
            )

            # eliminar líneas de bloque e instrucciones
            # en exámenes 2020+
            if year >= 2020:
                page_text = clean_page_text_2020_2024(page_text)

            else:  # examen 2010 - 2019
                # inserta una línea en blanco bajo cada ejercicio
                page_text = re.sub(r"(^\d{1}\.-)", r"\n\1", page_text, flags=re.MULTILINE)
                    
            exam_text += f"{page_text}"

    return exam_text


def split_exercises(exam_text: str, exam_period: str) -> list:
    """Divide el texto del examen en ejercicios.
    El parámetro year_period ajusta el nombre de los ejercicios
    acorde al periodo del examen:
    - 2010 - 2019: year_period = 2010-2019
    - 2020 - 2024: year_period = 2020-2024
    - 2025 - : year_period = 2025+
    """
    if exam_period not in ["2010-2019", "2020-2024", "2025+"]:
        raise ValueError("Código de año de examen incorrecto.")

    # pattern to split exercises
    # depending on exercise year period
    if exam_period == "2010-2019":
        pattern = r"^\d{1}\.-"  # 3.-
    elif exam_period == "2020-2024":
        pattern = r"^[ABC]\d{1}\."  # B2.
    else:
        pattern = r"^\d{1}[AB]\.|^PREGUNTA 5\.-"

    # extract exercise numbers
    exercise_numbers = re.findall(pattern, exam_text, flags=re.MULTILINE)

    # añadir opción si es examen 2010-2019
    if exam_period == "2010-2019":
        exercise_numbers_integer = [int(i.replace(".-", "")) for i in exercise_numbers]
        exercise_numbers = [f"{n}A" if n <= 5 else f"{n}B" for n in exercise_numbers_integer]
    
    # split exam_text using exercise number pattern
    exercises = re.split(pattern, exam_text, flags=re.M)

    # concatenate exercise number and exercise statement
    # exercises start from index 1
    exercises_list = [f"{ex_number}{exercise}" for ex_number, exercise in zip(exercise_numbers, exercises[1:])]

    # special exercise number for competencial exercise
    # in exams from 2024
    if exam_period == "2025+":
        # eliminar líneas que empiezan por "PREGUNTA"
        for idx, ex in enumerate(exercises_list):
            lines = []
            for line in ex.split("\n"):
                if line.startswith("PREGUNTA 5"):
                    line = "5"
                elif line.startswith("PREGUNTA"):
                    continue
                
                lines.append(line)
            
            ex = "\n".join(lines)
            ex = ex.split("PRUEBA DE ACCESO A LA UNIVERSIDAD")[0]
            exercises_list[idx] = ex

    return exercises_list


def get_exam_period(year):
    # ["2010-2019", "2020-2024", "2025+"]
    if year <= 2019:
        return "2010-2019"
    elif year <= 2024:
        return "2020-2024"
    else:
        return "2025+"



