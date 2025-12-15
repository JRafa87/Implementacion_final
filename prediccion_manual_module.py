import streamlit as st
import pandas as pd
import joblib
import shap
from supabase import create_client, Client
from typing import Dict, Any
import warnings
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# ==========================================================
# 🔴 CONFIGURACIÓN GENERAL
# ==========================================================

MODEL_PATH = "models/xgboost_model.pkl"
SCALER_PATH = "models/scaler.pkl"
MAPPING_PATH = "models/categorical_mapping.pkl"

EMPLOYEE_TABLE = "consolidado"
KEY_COLUMN = "EmployeeNumber"

# ==========================================================
# 🔴 VARIABLES DEL MODELO (ORDEN CORRECTO)
# ==========================================================

MODEL_COLUMNS = [
    "Age","BusinessTravel","Department","DistanceFromHome","Education",
    "EducationField","EnvironmentSatisfaction","Gender","JobInvolvement",
    "JobLevel","JobRole","JobSatisfaction","MaritalStatus","MonthlyIncome",
    "NumCompaniesWorked","OverTime","PercentSalaryHike","PerformanceRating",
    "RelationshipSatisfaction","TotalWorkingYears","TrainingTimesLastYear",
    "WorkLifeBalance","YearsAtCompany","YearsInCurrentRole",
    "YearsSinceLastPromotion","YearsWithCurrManager",
    "IntencionPermanencia","CargaLaboralPercibida","SatisfaccionSalarial",
    "ConfianzaEmpresa","NumeroTardanzas","NumeroFaltas","tipo_contrato"
]

# ==========================================================
# 🔒 VARIABLES BLOQUEADAS SI VIENEN DE BD
# ==========================================================

LOCKED_WHEN_FROM_DB = ["Age", "Gender", "MaritalStatus"]

# ==========================================================
# 🔴 SUPABASE
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
# 🔴 MODELO
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
# 🔴 PREDICCIÓN + SHAP
# ==========================================================

def predict_and_explain(data: Dict[str, Any]):
    df = pd.DataFrame([data]).reindex(columns=MODEL_COLUMNS, fill_value=0)

    for col, map_dict in mapping.items():
        if col in df.columns:
            df[col] = df[col].map(map_dict).fillna(0)

    df_scaled = scaler.transform(df)

    proba = model.predict_proba(df_scaled)[0][1]

    explainer = shap.Explainer(model)
    shap_values = explainer(df_scaled)

    shap_df = pd.DataFrame({
        "Variable": MODEL_COLUMNS,
        "Impacto": shap_values.values[0]
    }).assign(ImpactoAbs=lambda x: x["Impacto"].abs()) \
      .sort_values("ImpactoAbs", ascending=False) \
      .head(10)

    return proba, shap_df

# ==========================================================
# 🧠 UI PRINCIPAL (MODULO)
# ==========================================================

def render_manual_prediction_tab():

    st.title("📉 Predicción de Riesgo de Renuncia")
    st.caption("BASE desde Supabase + Simulación Manual + Explicabilidad")

    employee_ids = fetch_employee_ids()
    selected_id = st.selectbox(
        "Selecciona EmployeeNumber",
        ["--- Seleccionar ---"] + employee_ids
    )

    if selected_id != "--- Seleccionar ---":
        base_data = load_employee_data(selected_id)
        st.success(f"Empleado {selected_id} cargado")
    else:
        base_data = {}

    st.markdown("---")
    st.subheader("🧪 Simulación Manual (33 Variables)")
    st.caption("🔒 Edad, Género y Estado civil se bloquean si vienen de BD")

    manual_input = {}
    col1, col2 = st.columns(2)
    i = 0

    sliders = [
        "EnvironmentSatisfaction","JobSatisfaction","RelationshipSatisfaction",
        "WorkLifeBalance","IntencionPermanencia","CargaLaboralPercibida",
        "SatisfaccionSalarial","ConfianzaEmpresa"
    ]

    for col in MODEL_COLUMNS:
        base_val = base_data.get(col, 0)
        locked = col in LOCKED_WHEN_FROM_DB and selected_id != "--- Seleccionar ---"
        container = col1 if i % 2 == 0 else col2

        with container:
            label = f"{col} 🔒" if locked else col

            if col in sliders:
                manual_input[col] = st.slider(
                    label, 1, 5,
                    int(base_val) if base_val else 3,
                    disabled=locked
                )

            elif col in mapping:
                options = list(mapping[col].keys())
                default = base_val if base_val in options else options[0]
                manual_input[col] = st.selectbox(
                    label, options,
                    index=options.index(default),
                    disabled=locked
                )
            else:
                manual_input[col] = st.number_input(
                    label,
                    value=float(base_val) if base_val else 0.0,
                    disabled=locked
                )
        i += 1

    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📊 Predicción BASE")
        if st.button("🔮 Ejecutar BASE", use_container_width=True):
            prob, shap_df = predict_and_explain(base_data)
            st.metric("Probabilidad de Renuncia", f"{prob:.2%}")
            st.subheader("🧠 Variables que empujan la renuncia")
            st.bar_chart(shap_df.set_index("Variable")["Impacto"])

    with c2:
        st.subheader("🧪 Predicción MANUAL")
        if st.button("🧪 Ejecutar MANUAL", use_container_width=True):
            prob, shap_df = predict_and_explain(manual_input)
            st.metric("Probabilidad Simulada", f"{prob:.2%}")
            st.subheader("🧠 Variables que empujan la renuncia")
            st.bar_chart(shap_df.set_index("Variable")["Impacto"])


