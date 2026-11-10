
import streamlit as st
from pathlib import Path

ROOT = Path("~/code/selector_examenes").expanduser()

years = [int(i.name.split("_")[0]) for i in (ROOT / "examenes_quimica").iterdir() if i.is_dir()]

def get_available_pdf(folder):
    return sorted([i.stem.replace("_", " ").upper()
            for i in folder.iterdir()
            if i.suffix == ".pdf"])

st.title("Obtener ejercicios de examen de Selectividad")

selected_year = st.selectbox(label = "Año",
                             options=years,
                             index = None,
                             placeholder="Elige un año"
                             )

if selected_year:
    folder = Path(f"examenes_quimica/{selected_year}_quimica")

    selected_exam = st.selectbox(label="Examen",
                                 options = get_available_pdf(folder))



