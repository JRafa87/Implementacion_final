import streamlit as st
import pandas as pd
import joblib
import shap
import plotly.express as px
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

# Traducción de etiquetas de columnas para la UI
TRADUCCIONES_COLS = {
    "Age": "Edad", "BusinessTravel": "Viajes de Negocios", "Department": "Departamento",
    "DistanceFromHome": "Distancia desde Casa", "Education": "Nivel Educativo",
    "EducationField": "Campo de Estudio", "EnvironmentSatisfaction": "Satisfacción Ambiental",
    "Gender": "Género", "JobInvolvement": "Compromiso Laboral", "JobLevel": "Nivel de Puesto",
    "JobRole": "Cargo", "JobSatisfaction": "Satisfacción Laboral", "MaritalStatus": "Estado Civil",
    "MonthlyIncome": "Ingreso Mensual", "NumCompaniesWorked": "Empresas Anteriores",
    "OverTime": "Horas Extra", "PercentSalaryHike": "Aumento Salarial (%)", "PerformanceRating": "Desempeño",
    "RelationshipSatisfaction": "Satisfacción Relacional", "TotalWorkingYears": "Años Experiencia Total",
    "TrainingTimesLastYear": "Capacitaciones (Año pasado)", "WorkLifeBalance": "Equilibrio Vida-Trabajo",
    "YearsAtCompany": "Años en la Empresa", "YearsInCurrentRole": "Años en el Cargo",
    "YearsSinceLastPromotion": "Años desde último Ascenso", "YearsWithCurrManager": "Años con Jefe Actual",
    "IntencionPermanencia": "Intención de Permanencia", "CargaLaboralPercibida": "Carga Laboral",
    "SatisfaccionSalarial": "Satisfacción Salarial", "ConfianzaEmpresa": "Confianza en Empresa",
    "NumeroTardanzas": "Tardanzas", "NumeroFaltas": "Faltas", "tipo_contrato": "Tipo de Contrato"
}

# Traducción de valores internos (Original -> Español)
TRADUCCIONES_VALORES = {
    "Department": {
        "HR": "Recursos Humanos",
        "RESEARCH_AND_DEVELOPMENT": "Investigación y Desarrollo",
        "SALES": "Ventas"
    },
    "BusinessTravel": {
        "NON-TRAVEL": "Sin Viajes",
        "TRAVEL_FREQUENTLY": "Viajes Frecuentes",
        "TRAVEL_RARELY": "Viajes Ocasionales"
    },
    "EducationField": {
        "HUMAN_RESOURCES": "Recursos Humanos",
        "LIFE_SCIENCES": "Ciencias de la Vida",
        "MARKETING": "Marketing",
        "MEDICAL": "Medicina",
        "OTHER": "Otros",
        "TECHNICAL_DEGREE": "Grado Técnico"
    },
    "Gender": {
        "FEMALE": "Femenino",
        "MALE": "Masculino"
    },
    "JobRole": {
        "HEALTHCARE_REPRESENTATIVE": "Representante de Salud",
        "HUMAN_RESOURCES": "Recursos Humanos",
        "LABORATORY_TECHNICIAN": "Técnico de Laboratorio",
        "MANAGER": "Gerente",
        "MANUFACTURING_DIRECTOR": "Director de Manufactura",
        "RESEARCH_DIRECTOR": "Director de Investigación",
        "RESEARCH_SCIENTIST": "Científico de Investigación",
        "SALES_EXECUTIVE": "Ejecutivo de Ventas",
        "SALES_REPRESENTATIVE": "Representante de Ventas"
    },
    "MaritalStatus": {
        "DIVORCED": "Divorciado/a",
        "MARRIED": "Casado/a",
        "SINGLE": "Soltero/a"
    }
}

MODEL_COLUMNS = list(TRADUCCIONES_COLS.keys())
LOCKED_WHEN_FROM_DB = ["Age", "Gender", "MaritalStatus", "JobRole", "EducationField", "Department"]

# ==========================================================
# 2. CARGA DE RECURSOS
# ==========================================================

@st.cache_resource
def load_resources():
    return joblib.load(MODEL_PATH), joblib.load(SCALER_PATH), joblib.load(MAPPING_PATH)

model, scaler, mapping = load_resources()

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

# ==========================================================
# 3. PREDICCIÓN + SHAP CON COLORES
# ==========================================================

def predict_with_shap(data: Dict[str, Any]):
    df = pd.DataFrame([data]).reindex(columns=MODEL_COLUMNS, fill_value=0)
    
    # Procesamiento para el modelo
    for col, mp in mapping.items():
        if col in df.columns:
            df[col] = df[col].map(mp).fillna(0)
    
    df_scaled = scaler.transform(df)
    proba = model.predict_proba(df_scaled)[0][1]
    
    explainer = shap.Explainer(model)
    shap_values = explainer(df_scaled)
    
    # Crear DF para gráfico
    shap_df = pd.DataFrame({
        "Variable": [TRADUCCIONES_COLS.get(c, c) for c in MODEL_COLUMNS],
        "Impacto": shap_values.values[0]
    })
    
    # Lógica de colores: Rojo (+ riesgo), Verde (- riesgo)
    shap_df["Color"] = shap_df["Impacto"].apply(lambda x: "Riesgo (Sube)" if x > 0 else "Retención (Baja)")
    shap_df["Abs"] = shap_df["Impacto"].abs()
    shap_df = shap_df.sort_values("Abs", ascending=False).head(8)
    
    return proba, shap_df

# ==========================================================
# 4. INTERFAZ DE USUARIO
# ==========================================================

def render_manual_prediction_tab():
    st.title("📉 Comparador de Riesgo de Renuncia")
    
    st.session_state.setdefault("pred_base", None)
    st.session_state.setdefault("pred_manual", None)

    ids = fetch_employee_ids()
    selected_id = st.selectbox("👤 Seleccione ID del Colaborador", ["--- Seleccionar ---"] + ids)
    base_data = load_employee_data(selected_id) if selected_id != "--- Seleccionar ---" else {}

    st.divider()
    st.subheader("🧪 Simulación de Escenario Hipotético")

    manual_input = {}
    col1, col2 = st.columns(2)
    sliders = ["EnvironmentSatisfaction","JobSatisfaction","RelationshipSatisfaction","WorkLifeBalance",
               "IntencionPermanencia","CargaLaboralPercibida","SatisfaccionSalarial","ConfianzaEmpresa"]

    for i, col in enumerate(MODEL_COLUMNS):
        base_val = base_data.get(col, 0)
        locked = col in LOCKED_WHEN_FROM_DB and selected_id != "--- Seleccionar ---"
        container = col1 if i % 2 == 0 else col2
        label_es = TRADUCCIONES_COLS.get(col, col)

        with container:
            display_label = f"{label_es} 🔒" if locked else label_es
            
            if col in sliders:
                manual_input[col] = st.slider(display_label, 1, 5, int(base_val) if base_val else 3, disabled=locked)
            
            elif col in mapping:
                options_en = list(mapping[col].keys())
                traduccion_dict = TRADUCCIONES_VALORES.get(col, {})
                
                # Mapeo Inverso para la UI
                opciones_ui = {traduccion_dict.get(opt, opt): opt for opt in options_en}
                
                default_en = base_val if base_val in options_en else options_en[0]
                default_ui = next((k for k, v in opciones_ui.items() if v == default_en), list(opciones_ui.keys())[0])
                
                seleccion_ui = st.selectbox(display_label, list(opciones_ui.keys()), 
                                            index=list(opciones_ui.keys()).index(default_ui), 
                                            disabled=locked)
                manual_input[col] = opciones_ui[seleccion_ui]
            
            else:
                manual_input[col] = st.number_input(display_label, value=float(base_val) if base_val else 0.0, disabled=locked)

    st.divider()
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🏢 Ejecutar Estado ACTUAL", use_container_width=True, type="secondary"):
            if not base_data: st.error("Primero selecciona un empleado.")
            else: st.session_state["pred_base"] = predict_with_shap(base_data)
    with b2:
        if st.button("🧪 Ejecutar Escenario SIMULADO", use_container_width=True, type="primary"):
            st.session_state["pred_manual"] = predict_with_shap(manual_input)

    # ===================== RESULTADOS Y GRÁFICOS =====================
    if st.session_state["pred_base"] or st.session_state["pred_manual"]:
        st.header("📊 Comparativa de Resultados")
        c1, c2, c3 = st.columns(3)
        
        if st.session_state["pred_base"]:
            c1.metric("Riesgo ACTUAL", f"{st.session_state['pred_base'][0]:.2%}")
        if st.session_state["pred_manual"]:
            c2.metric("Riesgo SIMULADO", f"{st.session_state['pred_manual'][0]:.2%}")
        if st.session_state["pred_base"] and st.session_state["pred_manual"]:
            diff = st.session_state["pred_manual"][0] - st.session_state["pred_base"][0]
            c3.metric("Diferencia", f"{diff:+.2%}", delta_color="inverse")

        st.divider()
        st.subheader("🧠 ¿Qué factores empujan la decisión?")
        st.caption("Las barras ROJAS aumentan el riesgo de renuncia. Las barras VERDES ayudan a retener al colaborador.")

        col_a, col_b = st.columns(2)
        
        def plot_shap(df_shap, title):
            fig = px.bar(df_shap, x="Impacto", y="Variable", orientation='h',
                         color="Color", title=title,
                         color_discrete_map={"Riesgo (Sube)": "#ef5350", "Retención (Baja)": "#66bb6a"},
                         category_orders={"Variable": df_shap["Variable"].tolist()})
            fig.update_layout(showlegend=True, yaxis={'categoryorder':'total ascending'})
            return fig

        if st.session_state["pred_base"]:
            with col_a:
                st.plotly_chart(plot_shap(st.session_state["pred_base"][1], "Impacto: Estado ACTUAL"), use_container_width=True)
        
        if st.session_state["pred_manual"]:
            with col_b:
                st.plotly_chart(plot_shap(st.session_state["pred_manual"][1], "Impacto: Escenario SIMULADO"), use_container_width=True)

if __name__ == '__main__':
    st.set_page_config(page_title="IA Comparador RRHH", layout="wide")
    render_manual_prediction_tab()



