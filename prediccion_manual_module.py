import streamlit as st
import pandas as pd
import joblib
from supabase import create_client, Client
from typing import Dict, Any
import warnings

warnings.filterwarnings("ignore")

# ==========================================================
# 🔴 CRÍTICO 1: CONFIGURACIÓN GENERAL
# ==========================================================

st.set_page_config(
    page_title="Sistema de Predicción de Renuncia",
    layout="wide"
)

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
# 🔴 CRÍTICO 3: VARIABLES BLOQUEADAS (SOLO SI VIENEN DE BD)
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
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = get_supabase()

def fetch_employee_ids():
    res = supabase.table(EMPLOYEE_TABLE).select(KEY_COLUMN).execute()
    return sorted([str(r[KEY_COLUMN]) for r in res.data])

def load_employee_data(emp_id: str) -> Dict[str, Any]:
    res = (
        supabase
        .table(EMPLOYEE_TABLE)
        .select("*")
        .eq(KEY_COLUMN, emp_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else {}

# ==========================================================
# 🔴 CRÍTICO 5: CARGA DEL MODELO
# ==========================================================

@st.cache_resource
def load_model():
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    mapping = joblib.load(MAPPING_PATH)
    return model, scaler, mapping

model, scaler, mapping = load_model()

# ==========================================================
# 🔴 CRÍTICO 6: FUNCIÓN DE PREDICCIÓN
# ==========================================================

def predict(input_data: Dict[str, Any]) -> float:
    df = pd.DataFrame([input_data])[MODEL_COLUMNS]

    for col, map_dict in mapping.items():
        if col in df.columns:
            df[col] = df[col].map(map_dict).fillna(0)

    df_scaled = scaler.transform(df)
    return model.predict_proba(df_scaled)[0][1]

# ==========================================================
# 🔴 CRÍTICO 7: UI PRINCIPAL
# ==========================================================

st.title("📉 Sistema de Predicción de Riesgo de Renuncia")
st.caption("Predicción BASE desde Supabase + Simulación Manual editable")

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
    st.success(f"Datos cargados para el empleado {selected_id}")
else:
    base_data = {}

# ==========================================================
# 🔴 CRÍTICO 9: FORMULARIO MANUAL (33 VARIABLES – UI MEJORADA)
# ==========================================================

st.markdown("---")
st.subheader("🧪 Escenario Manual / Simulación")
st.caption("🔒 Edad, Género y Estado civil se bloquean si vienen de la base de datos")

manual_input = {}

col_left, col_right = st.columns(2)
i = 0

for col in MODEL_COLUMNS:
    base_value = base_data.get(col, 0)
    is_locked = col in LOCKED_WHEN_FROM_DB and selected_id != "--- Seleccionar ---"
    container = col_left if i % 2 == 0 else col_right

    with container:
        # 🎚️ Variables de escala
        if col in [
            'IntencionPermanencia', 'CargaLaboralPercibida',
            'SatisfaccionSalarial', 'ConfianzaEmpresa',
            'EnvironmentSatisfaction', 'JobSatisfaction',
            'RelationshipSatisfaction', 'WorkLifeBalance'
        ]:
            manual_input[col] = st.slider(
                f"{col} 🔒" if is_locked else col,
                1, 5,
                int(base_value) if base_value else 3,
                disabled=is_locked,
                help="Dato bloqueado desde BD" if is_locked else None,
                key=f"man_{col}"
            )

        # 🔽 Variables categóricas
        elif col in mapping:
            options = list(mapping[col].keys())
            default = base_value if base_value in options else options[0]

            manual_input[col] = st.selectbox(
                f"{col} 🔒" if is_locked else col,
                options,
                index=options.index(default),
                disabled=is_locked,
                help="Dato bloqueado desde BD" if is_locked else None,
                key=f"man_{col}"
            )

        # 🔢 Variables numéricas
        else:
            manual_input[col] = st.number_input(
                f"{col} 🔒" if is_locked else col,
                value=float(base_value) if base_value else 0.0,
                disabled=is_locked,
                help="Dato bloqueado desde BD" if is_locked else None,
                key=f"man_{col}"
            )
    i += 1

# ==========================================================
# 🔴 CRÍTICO 10: EJECUCIÓN DE LAS DOS PREDICCIONES
# ==========================================================

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Predicción BASE")
    if st.button("🔮 Ejecutar Predicción BASE", use_container_width=True):
        prob_base = predict(base_data)
        st.metric("Probabilidad de Renuncia", f"{prob_base:.2%}")

with col2:
    st.subheader("🧪 Predicción MANUAL")
    if st.button("🧪 Ejecutar Predicción Manual", use_container_width=True):
        prob_manual = predict(manual_input)
        st.metric("Probabilidad Simulada", f"{prob_manual:.2%}")

