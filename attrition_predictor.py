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

MAPEO_DEPTOS_VIEW = {"Sales": "Ventas", "Research & Development": "I+D", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES_VIEW = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}

# ============================================================================== 
# 2. CARGA DE MODELO Y ARTEFACTOS (Optimizado)
# ==============================================================================

@st.cache_resource
def load_model_artefacts():
    try:
        model = joblib.load('models/xgboost_model.pkl')
        categorical_mapping = joblib.load('models/categorical_mapping.pkl')
        scaler = joblib.load('models/scaler.pkl')
        return model, categorical_mapping, scaler
    except Exception as e:
        st.error(f"❌ Error al cargar modelo: {e}")
        return None, None, None

# ============================================================================== 
# 3. PREPROCESAMIENTO (Optimizado para evitar demoras)
# ==============================================================================

def preprocess_data(df, model_columns, categorical_mapping, scaler):
    df_processed = df.copy()

    # Creación rápida de columnas faltantes
    missing_cols = list(set(model_columns) - set(df_processed.columns))
    if missing_cols:
        df_processed = pd.concat([df_processed, pd.DataFrame(columns=missing_cols)], axis=1)

    # Imputación masiva
    numeric_cols = df_processed.select_dtypes(include=np.number).columns.intersection(model_columns)
    df_processed[numeric_cols] = df_processed[numeric_cols].fillna(0)

    # Mapeo de categorías
    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].astype(str).str.strip().str.upper()
            if col in categorical_mapping:
                df_processed[col] = df_processed[col].map(categorical_mapping[col])
            df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce').fillna(-1)

    df_for_scaling = df_processed[model_columns].fillna(0)

    try:
        scaled_data = scaler.transform(df_for_scaling)
        return pd.DataFrame(scaled_data, columns=model_columns, index=df.index)
    except Exception:
        return None

# ============================================================================== 
# 4. LÓGICA DE PREDICCIÓN
# ==============================================================================

def generar_recomendacion_personalizada(row):
    recs = []
    if row.get('IntencionPermanencia', 3) <= 2: recs.append("Reforzar desarrollo profesional.")
    if row.get('CargaLaboralPercibida', 3) >= 4: recs.append("Revisar carga laboral.")
    if row.get('SatisfaccionSalarial', 3) <= 2: recs.append("Evaluar ajustes salariales.")
    if row.get('ConfianzaEmpresa', 3) <= 2: recs.append("Fomentar confianza.")
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1: recs.append("Analizar ausentismo.")
    return " | ".join(recs) if recs else "Sin alertas."

def run_prediction_pipeline(df_raw, model, categorical_mapping, scaler):
    df_input = df_raw.copy()
    processed = preprocess_data(df_input.drop(columns=['Attrition'], errors='ignore'), MODEL_COLUMNS, categorical_mapping, scaler)
    if processed is None: return None 

    prob = model.predict_proba(processed)[:, 1]
    df_raw['Probabilidad_Renuncia'] = prob
    df_raw['Recomendacion'] = df_raw.apply(generar_recomendacion_personalizada, axis=1)
    return df_raw

# ============================================================================== 
# 5. CONEXIÓN SUPABASE (TTL de 10 min para eliminar delay)
# ==============================================================================

@st.cache_resource
def init_supabase_client():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

@st.cache_data(ttl=600)
def fetch_data_from_supabase(_client: Client):
    try:
        result = _client.table('consolidado').select('*').execute()
        return pd.DataFrame(result.data) if result.data else None
    except Exception:
        return None

# ============================================================================== 
# 6. VISUALIZACIÓN (Dashboard en Español)
# ==============================================================================

def display_results_and_demo(df_resultados: pd.DataFrame, source: str):
    if df_resultados is None or df_resultados.empty:
        st.info(f"💡 Pendiente de procesar predicción para: {source}")
        return
    
    st.markdown(f"### 📈 Dashboard de Riesgo ({source})")
    
    c1, c2, c3 = st.columns(3)
    total_altos = (df_resultados["Probabilidad_Renuncia"] > 0.5).sum()
    c1.metric("Analizados", len(df_resultados))
    with c2:
        if total_altos > 0: st.error(f"🔴 {total_altos} en riesgo crítico")
        else: st.success("🟢 Riesgo bajo control")
    c3.metric("Riesgo Promedio", f"{df_resultados['Probabilidad_Renuncia'].mean():.1%}")

    df_top10 = df_resultados.sort_values('Probabilidad_Renuncia', ascending=False).head(10).copy()
    df_top10['Department'] = df_top10['Department'].replace(MAPEO_DEPTOS_VIEW)
    df_top10['JobRole'] = df_top10['JobRole'].replace(MAPEO_ROLES_VIEW)

    st.write("**Top 10 Colaboradores con mayor riesgo**")
    cols = st.columns([1, 1.5, 2, 1.5, 1, 1])
    h = ["ID", "Departamento", "Puesto", "Sueldo", "Riesgo", "Acción"]
    for col, head in zip(cols, h): col.write(f"**{head}**")

    for i, row in df_top10.iterrows():
        r1, r2, r3, r4, r5, r6 = st.columns([1, 1.5, 2, 1.5, 1, 1])
        r1.write(row.get('EmployeeNumber', i+1))
        r2.write(row.get('Department'))
        r3.write(row.get('JobRole'))
        r4.write(f"S/. {row.get('MonthlyIncome', 0):,.0f}")
        
        p = row['Probabilidad_Renuncia']
        color = "#FFCDD2" if p > 0.5 else "#FFF59D" if p > 0.3 else "#C8E6C9"
        r5.markdown(f"<div style='background:{color}; text-align:center; border-radius:4px;'>{p:.1%}</div>", unsafe_allow_html=True)
        with r6:
            with st.popover("Ver"):
                for rec in row['Recomendacion'].split(" | "): st.write(f"• {rec}")

# ============================================================================== 
# 7. RENDERIZADO (Solución al cambio de pestaña)
# ==============================================================================

def render_predictor_page():
    model, mapping, scaler = load_model_artefacts()
    if not model: return

    # Usamos un KEY para que Streamlit mantenga el estado de la pestaña
    tab1, tab2 = st.tabs(["📂 Archivo Local", "☁️ Base de Datos Supabase"])

    with tab1:
        st.subheader("Predicción desde Archivo")
        file = st.file_uploader("Cargar CSV o Excel", type=["csv", "xlsx"], key="file_up")
        if file and st.button("🚀 Calcular desde Archivo", key="btn_arch"):
            df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
            st.session_state.df_archivo = run_prediction_pipeline(df_raw, model, mapping, scaler)
        
        if 'df_archivo' in st.session_state:
            display_results_and_demo(st.session_state.df_archivo, "Archivo")

    with tab2:
        st.subheader("Análisis de Tabla Consolidada")
        client = init_supabase_client()
        if client and st.button("🔄 Sincronizar y Calcular", key="btn_sb"):
            with st.spinner("Procesando..."):
                df_sb = fetch_data_from_supabase(client)
                if df_sb is not None:
                    # Guardamos el resultado en Session State
                    st.session_state.df_supabase = run_prediction_pipeline(df_sb, model, mapping, scaler)
                else:
                    st.error("No se pudieron obtener datos de la tabla 'consolidado'.")
        
        if 'df_supabase' in st.session_state:
            display_results_and_demo(st.session_state.df_supabase, "Supabase")

if __name__ == '__main__':
    render_predictor_page()

