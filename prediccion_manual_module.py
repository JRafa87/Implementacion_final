import streamlit as st
import pandas as pd
import joblib
import shap
from supabase import create_client, Client
from typing import Dict, Any
import warnings

warnings.filterwarnings("ignore")

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

MODEL_PATH = "models/xgboost_model.pkl"
SCALER_PATH = "models/scaler.pkl"
MAPPING_PATH = "models/categorical_mapping.pkl"

EMPLOYEE_TABLE = "consolidado"
KEY_COLUMN = "EmployeeNumber"

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

LOCKED_WHEN_FROM_DB = ["Age", "Gender", "MaritalStatus","JobRole","EducationField","Department"]

# ==========================================================
# SUPABASE
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
# MODELO
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
# PREDICCIÓN + SHAP
# ==========================================================

def predict_with_shap(data: Dict[str, Any]):
    df = pd.DataFrame([data]).reindex(columns=MODEL_COLUMNS, fill_value=0)

    for col, mp in mapping.items():
        if col in df.columns:
            df[col] = df[col].map(mp).fillna(0)

    df_scaled = scaler.transform(df)
    proba = model.predict_proba(df_scaled)[0][1]

    explainer = shap.Explainer(model)
    shap_values = explainer(df_scaled)

    shap_df = (
        pd.DataFrame({
            "Variable": MODEL_COLUMNS,
            "Impacto": shap_values.values[0]
        })
        .assign(Abs=lambda x: x.Impacto.abs())
        .sort_values("Abs", ascending=False)
        .head(8)
    )

    return proba, shap_df

# ==========================================================
# UI PRINCIPAL
# ==========================================================

def render_manual_prediction_tab():

    st.title("📉 Comparador de Riesgo de Renuncia")
    st.caption("Cada predicción se ejecuta de forma independiente")

    # Inicializar estados
    st.session_state.setdefault("pred_base", None)
    st.session_state.setdefault("pred_manual", None)

    employee_ids = fetch_employee_ids()
    selected_id = st.selectbox(
        "Selecciona EmployeeNumber",
        ["--- Seleccionar ---"] + employee_ids
    )

    base_data = load_employee_data(selected_id) if selected_id != "--- Seleccionar ---" else {}

    # ===================== FORMULARIO MANUAL =====================

    st.markdown("---")
    st.subheader("🧪 Simulación Manual")

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
                manual_input[col] = st.slider(label, 1, 5, int(base_val) if base_val else 3, disabled=locked)
            elif col in mapping:
                options = list(mapping[col].keys())
                default = base_val if base_val in options else options[0]
                manual_input[col] = st.selectbox(label, options, options.index(default), disabled=locked)
            else:
                manual_input[col] = st.number_input(label, value=float(base_val) if base_val else 0.0, disabled=locked)

        i += 1

    # ===================== BOTONES =====================

    st.markdown("---")
    b1, b2 = st.columns(2)

    with b1:
        if st.button("🏢 Ejecutar BASE", use_container_width=True):
            st.session_state["pred_base"] = predict_with_shap(base_data)

    with b2:
        if st.button("🧪 Ejecutar MANUAL", use_container_width=True):
            st.session_state["pred_manual"] = predict_with_shap(manual_input)

    # ===================== RESULTADOS =====================

    if st.session_state["pred_base"] or st.session_state["pred_manual"]:
        st.markdown("## 📊 Resultados")

        c1, c2, c3 = st.columns(3)

        if st.session_state["pred_base"]:
            prob_b, _ = st.session_state["pred_base"]
            c1.metric("🏢 BASE", f"{prob_b:.2%}")

        if st.session_state["pred_manual"]:
            prob_m, _ = st.session_state["pred_manual"]
            c2.metric("🧪 MANUAL", f"{prob_m:.2%}")

        if st.session_state["pred_base"] and st.session_state["pred_manual"]:
            diff = prob_m - prob_b
            c3.metric("📉 Diferencia", f"{diff:+.2%}")

        st.markdown("### 🧠 Variables que empujan la renuncia")

        col_a, col_b = st.columns(2)

        if st.session_state["pred_base"]:
            _, shap_b = st.session_state["pred_base"]
            with col_a:
                st.subheader("BASE")
                st.bar_chart(shap_b.set_index("Variable")["Impacto"])

        if st.session_state["pred_manual"]:
            _, shap_m = st.session_state["pred_manual"]
            with col_b:
                st.subheader("MANUAL")
                st.bar_chart(shap_m.set_index("Variable")["Impacto"])



