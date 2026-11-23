import re

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ejercicios", layout="wide")


TODOS = "Todos"



@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["statement"] = df["statement"]

    # El CSV no trae tema: si existe una columna 'tema' la usamos, si no queda vacía
    df["topic"] = df["topics"] if "tema" in df.columns else ""

    # Columna combinada: examen · ejercicio · opción  (p. ej. "J · 3 · A")
    df["exam_exercise_option"] = (
        df["exam"].fillna("?") + " · " + df["exercise"].fillna("?") + " · " + df["option"].fillna("?")
    )

    return df


def selector(label: str, serie: pd.Series) -> str:
    """Desplegable con 'Todos' + los valores únicos (ordenados) de la columna."""
    opciones = [TODOS] + sorted(serie.dropna().astype(str).unique())
    return st.selectbox(label, opciones)


df = load_data("examenes_oficiales_clasificados.csv")

st.title("Ejercicios")

# --- Selectores en una fila ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    year_sel = selector("Año", df["year"])
with col2:
    exam_sel = selector("Examen", df["exam"])
with col3:
    option_sel = selector("Opción", df["option"])
with col4:
    topic_sel = selector("Tema", df["topic"])

# --- Filtrado ---
filtrado = df
if year_sel != TODOS:
    filtrado = filtrado[filtrado["year"].astype(str) == year_sel]
if exam_sel != TODOS:
    filtrado = filtrado[filtrado["exam"] == exam_sel]
if option_sel != TODOS:
    filtrado = filtrado[filtrado["option"] == option_sel]
if topic_sel != TODOS:
    filtrado = filtrado[filtrado["topic"] == topic_sel]

st.caption(f"{len(filtrado)} de {len(df)} ejercicios")

st.dataframe(
    filtrado[["year", "exam_exercise_option", "topic", "statement"]],
    hide_index=True,
    use_container_width=True,
    column_config={
        "year": st.column_config.NumberColumn("Año", format="%d"),
        "exam_exercise_option": st.column_config.TextColumn("Examen · Ejercicio · Opción"),
        "topic": st.column_config.TextColumn("Tema"),
        "statement": st.column_config.TextColumn("Enunciado", width="large"),
    },
)
