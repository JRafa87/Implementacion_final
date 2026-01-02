import pandas as pd
import numpy as np
import joblib
import streamlit as st
from datetime import datetime
from typing import Optional

# Configuración de Supabase
try:
    from supabase import create_client, Client
    SUPABASE_INSTALLED = True
except ImportError:
    class Client: pass
    SUPABASE_INSTALLED = False

# ============================================================================== 
# 1. CONSTANTES Y MAPEOS DE TRADUCCIÓN
# ==============================================================================
MODEL_COLUMNS = [
    'Age', 'BusinessTravel', 'Department', 'DistanceFromHome', 'Education',
    'EducationField', 'EnvironmentSatisfaction', 'Gender', 'JobInvolvement', 
    'JobLevel', 'JobRole', 'JobSatisfaction', 'MaritalStatus', 'MonthlyIncome', 
    'NumCompaniesWorked', 'OverTime', 'PercentSalaryHike', 'PerformanceRating', 
    'RelationshipSatisfaction', 'TotalWorkingYears', 'TrainingTimesLastYear',
    'WorkLifeBalance', 'YearsAtCompany', 'YearsInCurrentRole', 
    'YearsSinceLastPromotion', 'YearsWithCurrManager', 'IntencionPermanencia', 
    'CargaLaboralPercibida', 'SatisfaccionSalarial', 'ConfianzaEmpresa', 
    'NumeroTardanzas', 'NumeroFaltas', 'tipo_contrato' 
]

CATEGORICAL_COLS_TO_MAP = ['BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole', 'MaritalStatus', 'OverTime', 'tipo_contrato']

MAPEO_DEPTOS_VIEW = {"Sales": "Ventas", "Research & Development": "I+D", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES_VIEW = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}

# ============================================================================== 
# 2. CARGA DE RECURSOS (Caché para eliminar Delay)
# ==============================================================================
@st.cache_resource
def load_resources():
    model = joblib.load('models/xgboost_model.pkl')
    mapping = joblib.load('models/categorical_mapping.pkl')
    scaler = joblib.load('models/scaler.pkl')
    return model, mapping, scaler

@st.cache_resource
def get_supabase():
    url, key = st.secrets.get("SUPABASE_URL"), st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

@st.cache_data(ttl=600)
def get_data_from_db(_client):
    res = _client.table('consolidado').select('*').execute()
    return pd.DataFrame(res.data) if res.data else None

# ============================================================================== 
# 3. LÓGICA DE NEGOCIO Y PREDICCIÓN
# ==============================================================================
def obtener_recomendaciones(row):
    r = []
    if row.get('IntencionPermanencia', 3) <= 2: r.append("Reforzar desarrollo profesional.")
    if row.get('CargaLaboralPercibida', 3) >= 4: r.append("Revisar carga laboral / Horas extra.")
    if row.get('SatisfaccionSalarial', 3) <= 2: r.append("Evaluar ajustes o bonos salariales.")
    if row.get('ConfianzaEmpresa', 3) <= 2: r.append("Fomentar transparencia y confianza.")
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1: r.append("Analizar causas de ausentismo.")
    return " | ".join(r) if r else "Sin alertas inmediatas."

def run_pipeline(df_raw, model, mapping, scaler):
    df_input = df_raw.copy()
    # Asegurar columnas para el modelo
    for col in MODEL_COLUMNS:
        if col not in df_input.columns: df_input[col] = 0
    
    # Preprocesamiento rápido
    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_input.columns:
            df_input[col] = df_input[col].astype(str).str.strip().str.upper().map(mapping.get(col, {})).fillna(-1)

    df_final = df_input[MODEL_COLUMNS].fillna(0)
    prob = model.predict_proba(scaler.transform(df_final))[:, 1]
    
    df_raw['Probabilidad_Renuncia'] = prob
    df_raw['Recomendacion'] = df_raw.apply(obtener_recomendaciones, axis=1)
    return df_raw

# ============================================================================== 
# 4. INTERFAZ DE USUARIO (Dashboard Traducido)
# ==============================================================================
def display_dashboard(df, source_name):
    st.markdown(f"### 📊 Dashboard de Riesgos: {source_name}")
    
    # Métricas de Alerta
    m1, m2, m3 = st.columns(3)
    criticos = len(df[df['Probabilidad_Renuncia'] > 0.5])
    m1.metric("Personal Analizado", f"{len(df)} pers.")
    with m2:
        if criticos > 0: st.error(f"🔴 {criticos} Casos Críticos (>50%)")
        else: st.success("🟢 Riesgo Bajo Control")
    m3.metric("Riesgo Promedio", f"{df['Probabilidad_Renuncia'].mean():.1%}")

    st.divider()
    st.subheader("👥 Top 10 Colaboradores con Mayor Probabilidad de Renuncia")
    
    # Preparar Top 10
    df_top = df.sort_values('Probabilidad_Renuncia', ascending=False).head(10).copy()
    df_top['Department'] = df_top['Department'].replace(MAPEO_DEPTOS_VIEW)
    df_top['JobRole'] = df_top['JobRole'].replace(MAPEO_ROLES_VIEW)

    # Encabezados de Tabla
    h_cols = st.columns([1, 1.5, 2, 1.5, 1, 1])
    headers = ["ID", "Departamento", "Puesto Actual", "Sueldo", "Riesgo", "Acción"]
    for col, text in zip(h_cols, headers): col.write(f"**{text}**")
    st.markdown("---")

    # Filas de Datos
    for i, row in df_top.iterrows():
        c1, c2, c3, c4, c5, c6 = st.columns([1, 1.5, 2, 1.5, 1, 1])
        c1.write(f"#{row.get('EmployeeNumber', i+1)}")
        c2.write(row.get('Department'))
        c3.write(row.get('JobRole'))
        c4.write(f"S/. {row.get('MonthlyIncome', 0):,.0f}")
        
        prob = row['Probabilidad_Renuncia']
        bg_color = "#FFCDD2" if prob > 0.5 else "#FFF59D" if prob > 0.3 else "#C8E6C9"
        c5.markdown(f"<div style='background:{bg_color}; color:black; text-align:center; border-radius:4px; font-weight:bold;'>{prob:.1%}</div>", unsafe_allow_html=True)
        
        with c6:
            with st.popover("🔍 Ver"):
                st.write("**📍 Recomendaciones:**")
                recs = row['Recomendacion'].split(" | ")
                for r in recs: st.write(f"- {r}")

def render_predictor_page():
    model, mapping, scaler = load_resources()
    
    # Persistencia de datos en la sesión para evitar que se borren al cambiar de pestaña
    if 'res_archivo' not in st.session_state: st.session_state.res_archivo = None
    if 'res_supabase' not in st.session_state: st.session_state.res_supabase = None

    tab1, tab2 = st.tabs(["📂 Predicción por Archivo", "☁️ Datos de Supabase"])

    with tab1:
        st.subheader("Subir Data Local")
        file = st.file_uploader("Formatos: CSV, XLSX", type=["csv", "xlsx"], key="u_file")
        if file and st.button("🚀 Ejecutar Análisis de Archivo", use_container_width=True):
            df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
            st.session_state.res_archivo = run_pipeline(df, model, mapping, scaler)
        
        if st.session_state.res_archivo is not None:
            display_dashboard(st.session_state.res_archivo, "Carga Local")

    with tab2:
        st.subheader("Análisis desde Base de Datos")
        client = get_supabase()
        if client and st.button("🔄 Sincronizar y Calcular Riesgos", use_container_width=True):
            with st.spinner("Conectando con Supabase..."):
                df_sb = get_data_from_db(client)
                if df_sb is not None:
                    st.session_state.res_supabase = run_pipeline(df_sb, model, mapping, scaler)
                else:
                    st.error("No se pudo obtener la tabla 'consolidado'.")
        
        if st.session_state.res_supabase is not None:
            display_dashboard(st.session_state.res_supabase, "Supabase Cloud")

if __name__ == '__main__':
    render_predictor_page()

