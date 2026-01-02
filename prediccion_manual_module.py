import streamlit as st
import pandas as pd
import joblib
import shap
from supabase import create_client, Client
from typing import Dict, Any
import warnings

warnings.filterwarnings("ignore")

# ==========================================================
# 1. CONFIGURACIÓN Y MAPEOS DE TRADUCCIÓN
# ==========================================================

MODEL_PATH = "models/xgboost_model.pkl"
SCALER_PATH = "models/scaler.pkl"
MAPPING_PATH = "models/categorical_mapping.pkl"

EMPLOYEE_TABLE = "consolidado"
KEY_COLUMN = "EmployeeNumber"

# Diccionario para mostrar nombres amigables en español
TRADUCCIONES = {
    "Age": "Edad", "BusinessTravel": "Viajes de Negocios", "Department": "Departamento",
    "DistanceFromHome": "Distancia desde Casa", "Education": "Nivel Educativo",
    "EducationField": "Campo de Estudio", "EnvironmentSatisfaction": "Satisfacción Ambiental",
    "Gender": "Género", "JobInvolvement": "Compromiso Laboral", "JobLevel": "Nivel de Puesto",
    "JobRole": "Cargo", "JobSatisfaction": "Satisfacción Laboral", "MaritalStatus": "Estado Civil",
    "MonthlyIncome": "Ingreso Mensual", "NumCompaniesWorked": "Empresas Anteriores",
    "OverTime": "Horas Extra", "PercentSalaryHike": "Aumento Salarial (%)", "PerformanceRating": "Evaluación de Desempeño",
    "RelationshipSatisfaction": "Satisfacción de Relaciones", "TotalWorkingYears": "Años Totales Laborados",
    "TrainingTimesLastYear": "Capacitaciones (Año pasado)", "WorkLifeBalance": "Equilibrio Vida-Trabajo",
    "YearsAtCompany": "Años en la Empresa", "YearsInCurrentRole": "Años en el Cargo Actual",
    "YearsSinceLastPromotion": "Años desde último Ascenso", "YearsWithCurrManager": "Años con Jefe Actual",
    "IntencionPermanencia": "Intención de Permanencia", "CargaLaboralPercibida": "Carga Laboral Percibida",
    "SatisfaccionSalarial": "Satisfacción Salarial", "ConfianzaEmpresa": "Confianza en la Empresa",
    "NumeroTardanzas": "Número de Tardanzas", "NumeroFaltas": "Número de Faltas", "tipo_contrato": "Tipo de Contrato"
}

MODEL_COLUMNS = list(TRADUCCIONES.keys())

# Variables que no se pueden editar si vienen de la DB
LOCKED_WHEN_FROM_DB = ["Age", "Gender", "MaritalStatus", "JobRole", "EducationField", "Department"]

# ==========================================================
# 2. CONEXIONES (SUPABASE Y MODELO)
# ==========================================================

@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

def fetch_employee_ids():
    res = supabase.table(EMPLOYEE_TABLE).select(KEY_COLUMN).execute()
    return sorted([str(r[KEY_COLUMN]) for r in res.data])

def load_employee_data(emp_id: str) -> Dict[str, Any]:
    res = supabase.table(EMPLOYEE_TABLE).select("*").eq(KEY_COLUMN, emp_id).limit(1).execute()
    return res.data[0] if res.data else {}

@st.cache_resource
def load_model_artefacts():
    return joblib.load(MODEL_PATH), joblib.load(SCALER_PATH), joblib.load(MAPPING_PATH)

model, scaler, mapping = load_model_artefacts()

# ==========================================================
# 3. LÓGICA DE PREDICCIÓN + SHAP (Interpretación)
# ==========================================================

def predict_with_shap(data: Dict[str, Any]):
    df = pd.DataFrame([data]).reindex(columns=MODEL_COLUMNS, fill_value=0)

    # Aplicar mapeos numéricos
    for col, mp in mapping.items():
        if col in df.columns:
            df[col] = df[col].map(mp).fillna(0)

    df_scaled = scaler.transform(df)
    proba = model.predict_proba(df_scaled)[0][1]

    # SHAP para explicar variables
    explainer = shap.Explainer(model)
    shap_values = explainer(df_scaled)

    shap_df = pd.DataFrame({
        "Variable": [TRADUCCIONES.get(c, c) for c in MODEL_COLUMNS], # Traducir para el gráfico
        "Impacto": shap_values.values[0]
    }).assign(Abs=lambda x: x.Impacto.abs()).sort_values("Abs", ascending=False).head(8)

    return proba, shap_df

# ==========================================================
# 4. INTERFAZ DE USUARIO (DASHBOARD COMPARATIVO)
# ==========================================================

def render_manual_prediction_tab():
    st.title("📉 Comparador de Riesgo de Renuncia")
    st.caption("Analice el estado actual versus un escenario hipotético (Simulación)")

    # Estados de sesión
    st.session_state.setdefault("pred_base", None)
    st.session_state.setdefault("pred_manual", None)

    # Selección de Colaborador
    ids = fetch_employee_ids()
    selected_id = st.selectbox("Seleccione ID del Colaborador", ["--- Seleccionar ---"] + ids)

    base_data = load_employee_data(selected_id) if selected_id != "--- Seleccionar ---" else {}

    st.markdown("---")
    st.subheader("🧪 Configuración de Simulación")
    st.info("Modifique los valores para ver cómo impactan en la probabilidad de renuncia.")

    manual_input = {}
    col1, col2 = st.columns(2)
    
    # Sliders de escala 1 a 5
    sliders = [
        "EnvironmentSatisfaction", "JobSatisfaction", "RelationshipSatisfaction",
        "WorkLifeBalance", "IntencionPermanencia", "CargaLaboralPercibida",
        "SatisfaccionSalarial", "ConfianzaEmpresa"
    ]

    for i, col in enumerate(MODEL_COLUMNS):
        base_val = base_data.get(col, 0)
        locked = col in LOCKED_WHEN_FROM_DB and selected_id != "--- Seleccionar ---"
        container = col1 if i % 2 == 0 else col2
        label_es = TRADUCCIONES.get(col, col)

        with container:
            display_label = f"{label_es} 🔒 (Fijo)" if locked else label_es

            if col in sliders:
                manual_input[col] = st.slider(display_label, 1, 5, int(base_val) if base_val else 3, disabled=locked)
            elif col in mapping:
                options = list(mapping[col].keys())
                # Manejar default en caso de que no exista en el mapping
                default_idx = options.index(base_val) if base_val in options else 0
                manual_input[col] = st.selectbox(display_label, options, index=default_idx, disabled=locked)
            else:
                manual_input[col] = st.number_input(display_label, value=float(base_val) if base_val else 0.0, disabled=locked)

    st.markdown("---")
    b1, b2 = st.columns(2)

    with b1:
        if st.button("🏢 Calcular Estado ACTUAL (Base)", use_container_width=True):
            if selected_id == "--- Seleccionar ---":
                st.warning("Seleccione un ID de colaborador primero.")
            else:
                st.session_state["pred_base"] = predict_with_shap(base_data)

    with b2:
        if st.button("🧪 Calcular Escenario SIMULADO", use_container_width=True):
            st.session_state["pred_manual"] = predict_with_shap(manual_input)

    # ===================== ÁREA DE RESULTADOS =====================

    if st.session_state["pred_base"] or st.session_state["pred_manual"]:
        st.markdown("## 📊 Comparativa de Resultados")

        c1, c2, c3 = st.columns(3)

        if st.session_state["pred_base"]:
            prob_b, _ = st.session_state["pred_base"]
            c1.metric("Probabilidad ACTUAL", f"{prob_b:.2%}")

        if st.session_state["pred_manual"]:
            prob_m, _ = st.session_state["pred_manual"]
            c2.metric("Probabilidad SIMULADA", f"{prob_m:.2%}")

        if st.session_state["pred_base"] and st.session_state["pred_manual"]:
            diff = prob_m - prob_b
            # Color verde si baja el riesgo, rojo si sube
            c3.metric("Diferencia de Riesgo", f"{diff:+.2%}", delta_color="inverse")

        st.divider()
        st.markdown("### 🧠 ¿Qué factores influyen más en el riesgo?")

        col_a, col_b = st.columns(2)

        if st.session_state["pred_base"]:
            _, shap_b = st.session_state["pred_base"]
            with col_a:
                st.markdown("**Motivos del Riesgo ACTUAL**")
                st.bar_chart(shap_b.set_index("Variable")["Impacto"])

        if st.session_state["pred_manual"]:
            _, shap_m = st.session_state["pred_manual"]
            with col_b:
                st.markdown("**Motivos del Riesgo SIMULADO**")
                st.bar_chart(shap_m.set_index("Variable")["Impacto"])

if __name__ == '__main__':
    st.set_page_config(page_title="IA Predictora", layout="wide")
    render_manual_prediction_tab()



