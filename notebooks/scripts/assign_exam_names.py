import streamlit as st
import pandas as pd
from pathlib import Path
import shutil

st.title("Asignar nombres de exámenes")

EXAMS_PATH = Path("../../examenes_quimica")

files = EXAMS_PATH.rglob(".pdf")

CONVOCATORIAS = ["Junio", "Julio"]





