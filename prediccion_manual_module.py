import streamlit as st
import pandas as pd
import joblib
import os
from supabase import create_client, Client
from typing import Dict, Any
from xgboost import XGBClassifier
import warnings

warnings.filterwarnings("ignore")

# ==========================================================
# 🔴 CRÍTICO 1: CONFIGURACIÓN GENERAL
# ==========================================================

MODEL_PATH = "models/xgboost_model.pkl"
SCALER_PATH = "models/scaler.pkl"
MAPPING_PATH = "models/categorical_mapping.pkl"

EMPLOYEE_TABLE = "consolidado"
KEY_COLUMN = "EmployeeNumber"

# ==========================================================
# 🔴 CRÍTICO 2: VARIABLES DEL MODELO (33)
# ==========================================================

MODEL_COLUMNS = [
    'Age', 'BusinessTravel', 'Department', 'DistanceFromHome', 'Education',
    'EducationField', 'EnvironmentSatisfaction', 'Gender', 'JobInvolvement',
    'JobLevel', 'JobRole', 'JobSatisfaction', 'MaritalStatus', 'MonthlyIncome',
    'NumCompaniesWorked', 'OverTime', 'PercentSalaryHike', 'PerformanceRating',
    'RelationshipSatisfaction', 'TotalWorkingYears', 'TrainingTimesLastYear',
    'WorkLifeBalance', 'YearsAtCompany', 'YearsInCurrentRole',
    'YearsSinceLastPromotion', 'YearsWithCurrManager',
    'IntencionPermanencia', 'CargaLaboralPercibida', 'SatisfaccionSalarial',
    'ConfianzaEmpresa', 'NumeroTardanzas', 'NumeroFaltas', 'tipo_contrato'
]

# ==========================================================
# 🔴 CRÍTICO 3: VARIABLES BLOQUEADAS
# ==========================================================

LOCKED_WHEN_FROM_DB = [
    'Age',
    'Gender',
    'MaritalStatus'
]

# ==========================================================
# 🔴 CRÍTICO 4: SUPABASE
# ==========================================================

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

def load_employee_data(emp_id: str) -> Dict[str, Any] | None:
    res = supabase.table(EMPLOYEE_TABLE).select("*").eq(KEY_COLUMN, emp_id).limit(1).execute()
    return res.data[0] if res.data else None

def fetch_employee_ids():
    res = supabase.table(EMPLOYEE_TABLE).select(KEY_COLUMN).execute()
    return sorted([str(r[KEY_COLUMN]) for r in res.data])

# ==========================================================
# 🔴 CRÍTICO 5: CARGA MODELO
# ==========================================================

@st.cache_resource
def load_model():
    return (
        joblib.load(MODEL_PATH),
        joblib.load(SCALER_PATH),
        joblib.load(MAPPING_PATH)
    )

model, scaler, mapping = load_model()

# ==========================================================
# 🔴 CRÍTICO 6: PREDICCIÓN
# ==========================================================

def predict(input_data: Dict[str, Any]):
    df = pd.DataFrame([input_data])[MODEL_COLUMNS]

    for col, map_dict in mapping.items():
        if col in df.columns:
            df[col] = df[col].map(map_dict).fillna(0)

    df_scaled = scaler.transform(df)
    proba = model.predict_proba(df_scaled)[0][1]
    return proba

# ==========================================================
# 🔴 CRÍTICO 7: UI PRINCIPAL
# ==========================================================

st.set_page_config(layout="wide")
st.title("📉 Sistema de Predicción de Renuncia")

employee_ids = fetch_employee_ids()
selected_id = st.selectbox(
    "Selecciona EmployeeNumber",
    ["--- Seleccionar ---"] + employee_ids
)

# ==========================================================
# 🔴 CRÍTICO 8: CARGA DE DATOS BASE
# ==========================================================

if selected_id != "--- Seleccionar ---":
    base_data = load_employee_data(selected_id)
    st.success(f"Datos cargados para empleado {selected_id}")
else:
    base_data = {}

# ==========================================================
# 🔴 CRÍTICO 9: FORMULARIO MANUAL (33 VARIABLES)
# ==========================================================

st.subheader("🧪 Escenario Manual (33 variables)")

manual_input = {}

for col in MODEL_COLUMNS:
    base_value = base_data.get(col, 0)
    is_locked = col in LOCKED_WHEN_FROM_DB and selected_id != "--- Seleccionar ---"

    if isinstance(base_value, (int, float)):
        manual_input[col] = st.number_input(
            col,
            value=float(base_value),
            disabled=is_locked,
            key=f"man_{col}"
        )
    else:
        manual_input[col] = st.text_input(
            col,
            value=str(base_value),
            disabled=is_locked,
            key=f"man_{col}"
        )

# ==========================================================
# 🔴 CRÍTICO 10: EJECUCIÓN DE LAS 2 PREDICCIONES
# ==========================================================

col1, col2 = st.columns(2)

with col1:
    if st.button("🔮 Predicción BASE (Supabase)", use_container_width=True):
        prob_base = predict(base_data)
        st.metric("Probabilidad de Renuncia", f"{prob_base:.2%}")

with col2:
    if st.button("🧪 Predicción MANUAL (Editable)", use_container_width=True):
        prob_manual = predict(manual_input)
        st.metric("Probabilidad Simulada", f"{prob_manual:.2%}")
