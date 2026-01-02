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

# Traducción de etiquetas de variables
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

# Traducción de los VALORES dentro de las categorías
TRADUCCIONES_VALORES = {
    "BusinessTravel": {"Travel_Rarely": "Viaja Poco", "Travel_Frequently": "Viaja Frecuentemente", "Non-Travel": "No Viaja"},
    "Department": {"Sales": "Ventas", "Research & Development": "I+D", "Human Resources": "Recursos Humanos"},
    "EducationField": {"Life Sciences": "Ciencias de la Vida", "Medical": "Medicina", "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos", "Other": "Otros"},
    "Gender": {"Male": "Masculino", "Female": "Femenino"},
    "JobRole": {
        "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
        "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director Manufactura",
        "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
        "Sales Representative": "Representante de Ventas", "Research Director": "Director Investigación",
        "Human Resources": "Recursos Humanos"
    },
    "MaritalStatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "OverTime": {"Yes": "Sí", "No": "No"},
    "tipo_contrato": {"Indefinido": "Indefinido", "Temporal": "Temporal"} # Ajustar según tus datos
}

MODEL_COLUMNS = list(TRADUCCIONES_COLS.keys())
LOCKED_WHEN_FROM_DB = ["Age", "Gender", "MaritalStatus","JobRole","EducationField","Department"]

# ==========================================================
# 2. CONEXIÓN Y MODELO
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
# 3. PREDICCIÓN + SHAP
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
    
    shap_df = pd.DataFrame({
        "Variable": [TRADUCCIONES_COLS.get(c, c) for c in MODEL_COLUMNS],
        "Impacto": shap_values.values[0]
    }).assign(Abs=lambda x: x.Impacto.abs()).sort_values("Abs", ascending=False).head(8)
    
    return proba, shap_df

# ==========================================================
# 4. UI COMPARADOR
# ==========================================================

def render_manual_prediction_tab():
    st.title("📉 Comparador de Riesgo de Renuncia")
    
    st.session_state.setdefault("pred_base", None)
    st.session_state.setdefault("pred_manual", None)

    ids = fetch_employee_ids()
    selected_id = st.selectbox("Seleccione EmployeeNumber", ["--- Seleccionar ---"] + ids)
    base_data = load_employee_data(selected_id) if selected_id != "--- Seleccionar ---" else {}

    st.markdown("---")
    st.subheader("🧪 Simulación de Escenarios")

    manual_input = {}
    col1, col2 = st.columns(2)
    sliders = ["EnvironmentSatisfaction","JobSatisfaction","RelationshipSatisfaction","WorkLifeBalance","IntencionPermanencia","CargaLaboralPercibida","SatisfaccionSalarial","ConfianzaEmpresa"]

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
                # Obtener opciones originales del mapeo (inglés)
                options_en = list(mapping[col].keys())
                # Crear diccionario inverso para mostrar en español pero guardar en inglés
                traduccion_opciones = TRADUCCIONES_VALORES.get(col, {})
                
                # Mostramos en español pero mapeamos al valor original que el modelo entiende
                # Si no hay traducción, usamos el valor original
                opciones_display = {traduccion_opciones.get(opt, opt): opt for opt in options_en}
                
                default_val_en = base_val if base_val in options_en else options_en[0]
                default_display = next((k for k, v in opciones_display.items() if v == default_val_en), list(opciones_display.keys())[0])
                
                seleccion_es = st.selectbox(display_label, list(opciones_display.keys()), index=list(opciones_display.keys()).index(default_display), disabled=locked)
                manual_input[col] = opciones_display[seleccion_es]
            
            else:
                manual_input[col] = st.number_input(display_label, value=float(base_val) if base_val else 0.0, disabled=locked)

    st.markdown("---")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🏢 Ejecutar ACTUAL", use_container_width=True):
            if not base_data: st.error("Seleccione un empleado")
            else: st.session_state["pred_base"] = predict_with_shap(base_data)
    with b2:
        if st.button("🧪 Ejecutar SIMULACIÓN", use_container_width=True):
            st.session_state["pred_manual"] = predict_with_shap(manual_input)

    # RESULTADOS
    if st.session_state["pred_base"] or st.session_state["pred_manual"]:
        st.markdown("## 📊 Comparativa")
        c1, c2, c3 = st.columns(3)
        if st.session_state["pred_base"]:
            c1.metric("Probabilidad ACTUAL", f"{st.session_state['pred_base'][0]:.2%}")
        if st.session_state["pred_manual"]:
            c2.metric("Probabilidad SIMULADA", f"{st.session_state['pred_manual'][0]:.2%}")
        if st.session_state["pred_base"] and st.session_state["pred_manual"]:
            diff = st.session_state["pred_manual"][0] - st.session_state["pred_base"][0]
            c3.metric("Diferencia", f"{diff:+.2%}", delta_color="inverse")

        st.markdown("### 🧠 Impacto de Variables")
        col_a, col_b = st.columns(2)
        if st.session_state["pred_base"]:
            with col_a:
                st.write("**Estado Actual**")
                st.bar_chart(st.session_state["pred_base"][1].set_index("Variable")["Impacto"])
        if st.session_state["pred_manual"]:
            with col_b:
                st.write("**Simulación**")
                st.bar_chart(st.session_state["pred_manual"][1].set_index("Variable")["Impacto"])

if __name__ == '__main__':
    st.set_page_config(page_title="IA Comparador", layout="wide")
    render_manual_prediction_tab()



