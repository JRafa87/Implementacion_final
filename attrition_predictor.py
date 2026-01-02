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
# 1. CONSTANTES Y MAPEOS
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

MAPEO_DEPTOS_VIEW = {"Sales": "Ventas", "Research & Development": "Investigación y Desarrollo", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES_VIEW = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}

# ============================================================================== 
# 2. FUNCIONES CORE (Caché para eliminar Delay)
# ==============================================================================
@st.cache_resource
def load_model_artefacts():
    return joblib.load('models/xgboost_model.pkl'), joblib.load('models/categorical_mapping.pkl'), joblib.load('models/scaler.pkl')

@st.cache_resource
def get_supabase_client():
    url, key = st.secrets.get("SUPABASE_URL"), st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

@st.cache_data(ttl=600)
def fetch_supabase_data(_client):
    res = _client.table('consolidado').select('*').execute()
    return pd.DataFrame(res.data) if res.data else None

def run_prediction_pipeline(df_raw, model, mapping, scaler):
    df_input = df_raw.copy()
    # Preprocesamiento rápido
    for col in MODEL_COLUMNS:
        if col not in df_input.columns: df_input[col] = 0
    
    numeric_cols = df_input.select_dtypes(include=np.number).columns.intersection(MODEL_COLUMNS)
    df_input[numeric_cols] = df_input[numeric_cols].fillna(0)

    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_input.columns:
            df_input[col] = df_input[col].astype(str).str.strip().str.upper().map(mapping.get(col, {})).fillna(-1)

    df_final = df_input[MODEL_COLUMNS].fillna(0)
    prob = model.predict_proba(scaler.transform(df_final))[:, 1]
    
    df_raw['Probabilidad_Renuncia'] = prob
    return df_raw

# ============================================================================== 
# 3. INTERFAZ (Solución de Pestañas y Delay)
# ==============================================================================
def render_predictor_page():
    # Carga inicial silenciosa
    model, mapping, scaler = load_model_artefacts()
    client = get_supabase_client()

    # --- Gestión de Estado para Pestañas ---
    if 'current_tab' not in st.session_state: st.session_state.current_tab = 0
    
    # st.tabs no soporta 'index', así que usamos radio o botones tipo tabs si el problema persiste, 
    # pero aquí forzamos la persistencia con session_state en los botones.
    
    tab_list = ["📂 Archivo Local", "☁️ Base de Datos Supabase"]
    tab_file, tab_sb = st.tabs(tab_list)

    # LÓGICA TAB 1: ARCHIVO
    with tab_file:
        st.subheader("Cargar Datos Externos")
        file = st.file_uploader("Subir CSV/Excel", type=["csv", "xlsx"])
        if file:
            if st.button("🚀 Predecir Archivo"):
                df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
                st.session_state.df_res = run_prediction_pipeline(df, model, mapping, scaler)
                st.session_state.source = "Archivo"
                # No necesitamos rerun, el estado ya cambió
        
        if st.session_state.get('source') == "Archivo":
            display_results(st.session_state.get('df_res'), "Archivo")

    # LÓGICA TAB 2: SUPABASE
    with tab_sb:
        st.subheader("Datos desde la Nube")
        if st.button("🔄 Sincronizar y Calcular"):
            with st.spinner("Obteniendo datos..."):
                df_sb = fetch_supabase_data(client)
                if df_sb is not None:
                    st.session_state.df_res_sb = run_prediction_pipeline(df_sb, model, mapping, scaler)
                    st.session_state.source_sb = "Supabase"
                else:
                    st.error("Error al conectar con Supabase.")
        
        if st.session_state.get('source_sb') == "Supabase":
            display_results(st.session_state.get('df_res_sb'), "Supabase")

def display_results(df, source):
    """Muestra los resultados formateados en español."""
    st.divider()
    st.markdown(f"#### 📊 Resultados: {source}")
    
    # Métricas rápidas
    m1, m2 = st.columns(2)
    m1.metric("Promedio Riesgo", f"{df['Probabilidad_Renuncia'].mean():.1%}")
    m2.metric("Casos Críticos", len(df[df['Probabilidad_Renuncia'] > 0.5]))

    # Top 10 traducido
    df_top = df.sort_values('Probabilidad_Renuncia', ascending=False).head(10).copy()
    df_top['Department'] = df_top['Department'].replace(MAPEO_DEPTOS_VIEW)
    df_top['JobRole'] = df_top['JobRole'].replace(MAPEO_ROLES_VIEW)

    # Renderizado de tabla manual para control total
    cols = st.columns([1, 2, 2, 1, 1])
    headers = ["ID", "Departamento", "Rol", "Sueldo", "Riesgo"]
    for col, h in zip(cols, headers): col.write(f"**{h}**")

    for _, row in df_top.iterrows():
        c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 1, 1])
        c1.write(row.get('EmployeeNumber', '-'))
        c2.write(row.get('Department'))
        c3.write(row.get('JobRole'))
        c4.write(f"S/. {row.get('MonthlyIncome', 0):,.0f}")
        
        p = row['Probabilidad_Renuncia']
        color = "🔴" if p > 0.5 else "🟡" if p > 0.3 else "🟢"
        c5.write(f"{color} {p:.1%}")

if __name__ == '__main__':
    render_predictor_page()

