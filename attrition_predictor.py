import pandas as pd
import numpy as np
import joblib
import streamlit as st
from datetime import datetime
from typing import Optional

# Obligatorio para la funcionalidad de Supabase
try:
    from supabase import create_client, Client
    SUPABASE_INSTALLED = True
except ImportError:
    class Client:
        pass
    SUPABASE_INSTALLED = False

# ============================================================================== 
# 1. CONSTANTES, CONFIGURACIÓN Y MAPEOS
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

CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]

# MAPEOS PARA VISUALIZACIÓN EN ESPAÑOL
MAPEO_DEPTOS_VIEW = {"Sales": "Ventas", "Research & Development": "Investigción y Desarrollo", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES_VIEW = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}

# ============================================================================== 
# 2. CARGA DE MODELO Y ARTEFACTOS
# ==============================================================================

@st.cache_resource
def load_model_artefacts():
    try:
        model = joblib.load('models/xgboost_model.pkl')
        categorical_mapping = joblib.load('models/categorical_mapping.pkl')
        scaler = joblib.load('models/scaler.pkl')
        return model, categorical_mapping, scaler
    except Exception as e:
        st.error(f"❌ Error al cargar modelo o artefactos: {e}")
        return None, None, None

# ============================================================================== 
# 3. PREPROCESAMIENTO (Mantiene idioma original para el modelo)
# ==============================================================================

def preprocess_data(df, model_columns, categorical_mapping, scaler):
    df_processed = df.copy()

    for col in model_columns:
        if col not in df_processed.columns:
            df_processed[col] = np.nan

    numeric_cols = df_processed.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if col in model_columns:
            df_processed[col] = df_processed[col].fillna(df_processed[col].mean() if not df_processed[col].isnull().all() else 0)

    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].astype(str).str.strip().str.upper()
            if col in categorical_mapping and categorical_mapping[col] is not None:
                df_processed[col] = df_processed[col].map(categorical_mapping[col])
            df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce').fillna(-1)

    df_for_scaling = df_processed[model_columns].fillna(0)

    try:
        if scaler is None: return None
        scaled_data = scaler.transform(df_for_scaling)
        return pd.DataFrame(scaled_data, columns=model_columns, index=df.index)
    except Exception as e:
        st.error(f"⚠️ Error al escalar datos: {e}")
        return None

# ============================================================================== 
# 4. PREDICCIÓN Y RECOMENDACIONES (En Español)
# ==============================================================================

def generar_recomendacion_personalizada(row):
    recomendaciones = []
    if row.get('IntencionPermanencia', 3) <= 2: recomendaciones.append("Reforzar desarrollo profesional.")
    if row.get('CargaLaboralPercibida', 3) >= 4: recomendaciones.append("Revisar carga laboral.")
    if row.get('SatisfaccionSalarial', 3) <= 2: recomendaciones.append("Evaluar ajustes salariales.")
    if row.get('ConfianzaEmpresa', 3) <= 2: recomendaciones.append("Fomentar confianza.")
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1: recomendaciones.append("Analizar ausentismo.")
    return " | ".join(recomendaciones) if recomendaciones else "Sin alertas."

def run_prediction_pipeline(df_raw, model, categorical_mapping, scaler):
    df_original = df_raw.copy()
    processed = preprocess_data(df_original.drop(columns=['Attrition'], errors='ignore'), MODEL_COLUMNS, categorical_mapping, scaler)
    
    if processed is None: return None 

    prob = model.predict_proba(processed)[:, 1]
    df_original['Probabilidad_Renuncia'] = prob
    df_original['Recomendacion'] = df_original.apply(generar_recomendacion_personalizada, axis=1)
    return df_original

# ============================================================================== 
# 5. CONEXIÓN SUPABASE (Optimizado con Cache)
# ==============================================================================

@st.cache_resource
def init_supabase_client():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

@st.cache_data(ttl=300)
def fetch_data_from_supabase(_client: Client):
    try:
        result = _client.table('consolidado').select('*').execute()
        return pd.DataFrame(result.data) if result.data else None
    except Exception as e:
        st.error(f"Error Supabase: {e}")
        return None

# ============================================================================== 
# 6. VISUALIZACIÓN EN ESPAÑOL (Dashboard)
# ==============================================================================

def display_results_and_demo(df_resultados: pd.DataFrame, source: Optional[str]):
    if df_resultados is None or df_resultados.empty:
        st.info("💡 Ejecuta una predicción para visualizar los resultados.")
        return
    
    st.markdown(f"<h2 style='text-align:center;'>📈 Dashboard de Riesgo de Rotación ({source})</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    total_altos = (df_resultados["Probabilidad_Renuncia"] > 0.5).sum()
    c1.metric("Total Analizados", f"{len(df_resultados)} pers.")
    with c2:
        if total_altos > 0: st.error(f"🔴 {total_altos} en riesgo crítico (>50%)")
        else: st.success("🟢 Riesgo controlado")
    c3.metric("Riesgo Promedio", f"{df_resultados['Probabilidad_Renuncia'].mean():.1%}")

    st.subheader("👥 Top 10 Colaboradores con Mayor Riesgo")
    df_top10 = df_resultados.sort_values('Probabilidad_Renuncia', ascending=False).head(10).copy()
    
    # Traducción para la vista
    df_top10['Department'] = df_top10['Department'].replace(MAPEO_DEPTOS_VIEW)
    df_top10['JobRole'] = df_top10['JobRole'].replace(MAPEO_ROLES_VIEW)

    # Tabla Maquetada
    cols = st.columns([1, 1.5, 2, 1.5, 1, 1])
    headers = ["ID", "Departamento", "Puesto", "Sueldo", "Riesgo", "Acción"]
    for col, h in zip(cols, headers): col.write(f"**{h}**")
    st.markdown("---")

    for i, row in df_top10.iterrows():
        r1, r2, r3, r4, r5, r6 = st.columns([1, 1.5, 2, 1.5, 1, 1])
        r1.write(f"#{row.get('EmployeeNumber', i+1)}")
        r2.write(row.get('Department'))
        r3.write(row.get('JobRole'))
        r4.write(f"S/. {row.get('MonthlyIncome', 0):,.0f}")
        
        prob = row['Probabilidad_Renuncia']
        color = "#FFCDD2" if prob > 0.5 else "#FFF59D" if prob > 0.3 else "#C8E6C9"
        r5.markdown(f"<div style='background:{color}; text-align:center; border-radius:5px;'>{prob:.1%}</div>", unsafe_allow_html=True)
        
        with r6:
            with st.popover("🔍 Ver"):
                st.write("**Estrategia:**")
                for rec in row['Recomendacion'].split(" | "): st.write(f"- {rec}")

# ============================================================================== 
# 7. RENDERIZADO DEL MÓDULO
# ==============================================================================

def render_predictor_page():
    model, mapping, scaler = load_model_artefacts()
    if not model: return

    tab1, tab2 = st.tabs(["📂 Predicción por Archivo", "☁️ Datos de Supabase (Consolidado)"])

    with tab1:
        st.subheader("Subir Data Local")
        file = st.file_uploader("CSV o Excel", type=["csv", "xlsx"])
        if file and st.button("🚀 Procesar Archivo", use_container_width=True):
            df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
            res = run_prediction_pipeline(df_raw, model, mapping, scaler)
            st.session_state.df_archivo = res
        
        if 'df_archivo' in st.session_state:
            display_results_and_demo(st.session_state.df_archivo, "Archivo Local")

    with tab2:
        st.subheader("Análisis en Tiempo Real")
        client = init_supabase_client()
        if client and st.button("🔄 Sincronizar y Predecir", use_container_width=True):
            with st.spinner("Consultando Supabase..."):
                df_sb = fetch_data_from_supabase(client)
                if df_sb is not None:
                    st.session_state.df_supabase = run_prediction_pipeline(df_sb, model, mapping, scaler)
        
        if 'df_supabase' in st.session_state:
            display_results_and_demo(st.session_state.df_supabase, "Supabase")

if __name__ == '__main__':
    st.set_page_config(page_title="IA Predictora", layout="wide")
    render_predictor_page()


