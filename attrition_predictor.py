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
# 1. RECURSOS Y MAPEOS (Caché para eliminar Delay)
# ==============================================================================
MAPEO_DEPTOS_VIEW = {"Sales": "Ventas", "Research & Development": "I+D", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES_VIEW = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}

@st.cache_resource
def load_resources():
    return (joblib.load('models/xgboost_model.pkl'), 
            joblib.load('models/categorical_mapping.pkl'), 
            joblib.load('models/scaler.pkl'))

@st.cache_resource
def get_supabase():
    url, key = st.secrets.get("SUPABASE_URL"), st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

@st.cache_data(ttl=600)
def get_data_from_db(_client):
    res = _client.table('consolidado').select('*').execute()
    return pd.DataFrame(res.data) if res.data else None

# ============================================================================== 
# 2. LÓGICA DE PREDICCIÓN
# ==============================================================================
def obtener_recomendaciones(row):
    r = []
    if row.get('IntencionPermanencia', 3) <= 2: r.append("Reforzar desarrollo profesional.")
    if row.get('CargaLaboralPercibida', 3) >= 4: r.append("Revisar carga laboral.")
    if row.get('SatisfaccionSalarial', 3) <= 2: r.append("Evaluar ajustes salariales.")
    if row.get('ConfianzaEmpresa', 3) <= 2: r.append("Fomentar confianza.")
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1: r.append("Analizar ausentismo.")
    return " | ".join(r) if r else "Sin alertas."

def run_pipeline(df_raw, model, mapping, scaler):
    df_input = df_raw.copy()
    model_cols = [
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
    for col in model_cols:
        if col not in df_input.columns: df_input[col] = 0
    
    cat_cols = ['BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole', 'MaritalStatus', 'OverTime', 'tipo_contrato']
    for col in cat_cols:
        if col in df_input.columns:
            df_input[col] = df_input[col].astype(str).str.strip().str.upper().map(mapping.get(col, {})).fillna(-1)

    df_final = df_input[model_cols].fillna(0)
    prob = model.predict_proba(scaler.transform(df_final))[:, 1]
    df_raw['Probabilidad_Renuncia'] = prob
    df_raw['Recomendacion'] = df_raw.apply(obtener_recomendaciones, axis=1)
    return df_raw

# ============================================================================== 
# 3. INTERFAZ (Solución estable al cambio de pestañas)
# ==============================================================================
def display_dashboard(df, title):
    st.markdown(f"### 📊 {title}")
    m1, m2, m3 = st.columns(3)
    criticos = len(df[df['Probabilidad_Renuncia'] > 0.5])
    m1.metric("Analizados", len(df))
    with m2:
        if criticos > 0: st.error(f"🔴 {criticos} Críticos")
        else: st.success("🟢 Riesgo Bajo")
    m3.metric("Riesgo Promedio", f"{df['Probabilidad_Renuncia'].mean():.1%}")

    st.subheader("👥 Top 10 Colaboradores con Mayor Riesgo")
    df_top = df.sort_values('Probabilidad_Renuncia', ascending=False).head(10).copy()
    df_top['Department'] = df_top['Department'].replace(MAPEO_DEPTOS_VIEW)
    df_top['JobRole'] = df_top['JobRole'].replace(MAPEO_ROLES_VIEW)

    # Tabla optimizada
    h_cols = st.columns([1, 1.5, 2, 1.5, 1, 1])
    for col, text in zip(h_cols, ["ID", "Depto", "Puesto", "Sueldo", "Riesgo", "Acción"]):
        col.write(f"**{text}**")
    
    for i, row in df_top.iterrows():
        c1, c2, c3, c4, c5, c6 = st.columns([1, 1.5, 2, 1.5, 1, 1])
        c1.write(row.get('EmployeeNumber', i+1))
        c2.write(row.get('Department'))
        c3.write(row.get('JobRole'))
        c4.write(f"S/. {row.get('MonthlyIncome', 0):,.0f}")
        p = row['Probabilidad_Renuncia']
        color = "#FFCDD2" if p > 0.5 else "#FFF59D" if p > 0.3 else "#C8E6C9"
        c5.markdown(f"<div style='background:{color}; text-align:center; border-radius:4px;'>{p:.1%}</div>", unsafe_allow_html=True)
        with c6:
            with st.popover("Ver"):
                for r in row['Recomendacion'].split(" | "): st.write(f"• {r}")

def render_predictor_page():
    model, mapping, scaler = load_resources()
    
    # --- NAVEGACIÓN ESTABLE ---
    # Usamos un Selectbox en lugar de Tabs para evitar el salto automático
    st.sidebar.title("Configuración")
    opcion = st.sidebar.selectbox("Seleccione Fuente de Datos", ["📁 Archivo Local", "☁️ Supabase Cloud"])

    if "res_archivo" not in st.session_state: st.session_state.res_archivo = None
    if "res_supabase" not in st.session_state: st.session_state.res_supabase = None

    if opcion == "📁 Archivo Local":
        st.header("Predicción por Archivo")
        file = st.file_uploader("Cargar CSV o Excel", type=["csv", "xlsx"])
        if file and st.button("🚀 Ejecutar Predicción"):
            df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
            st.session_state.res_archivo = run_pipeline(df, model, mapping, scaler)
        
        if st.session_state.res_archivo is not None:
            display_dashboard(st.session_state.res_archivo, "Resultados de Archivo")

    elif opcion == "☁️ Supabase Cloud":
        st.header("Predicción desde Base de Datos")
        client = get_supabase()
        if client and st.button("🔄 Sincronizar y Predecir"):
            with st.spinner("Procesando..."):
                df_sb = get_data_from_db(client)
                if df_sb is not None:
                    st.session_state.res_supabase = run_pipeline(df_sb, model, mapping, scaler)
                else:
                    st.error("No se pudo conectar con la tabla 'consolidado'.")
        
        if st.session_state.res_supabase is not None:
            display_dashboard(st.session_state.res_supabase, "Resultados en Tiempo Real (Supabase)")

if __name__ == '__main__':
    render_predictor_page()

