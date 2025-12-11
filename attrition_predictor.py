import pandas as pd
import numpy as np
import joblib
import streamlit as st
import plotly.express as px
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
# 1. CONSTANTES Y CONFIGURACIÓN
# ==============================================================================

MODEL_COLUMNS = [
    'Age','BusinessTravel','DailyRate','Department','DistanceFromHome',
    'Education','EducationField','EnvironmentSatisfaction','Gender','HourlyRate',
    'JobInvolvement','JobLevel','JobRole','JobSatisfaction','MaritalStatus',
    'MonthlyIncome','MonthlyRate','NumCompaniesWorked','OverTime','PercentSalaryHike',
    'PerformanceRating','RelationshipSatisfaction','StockOptionLevel','TotalWorkingYears',
    'TrainingTimesLastYear','WorkLifeBalance','YearsAtCompany','YearsInCurrentRole',
    'YearsSinceLastPromotion','YearsWithCurrManager',
    'IntencionPermanencia','CargaLaboralPercibida','SatisfaccionSalarial',
    'ConfianzaEmpresa','NumeroTardanzas','NumeroFaltas', 
    'tipo_contrato' 
]

CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]

# ============================================================================== 
# 2. CARGA DE MODELO Y ARTEFACTOS
# ==============================================================================

@st.cache_resource
def load_model_artefacts():
    try:
        model = joblib.load('models/xgboost_model.pkl')
        categorical_mapping = joblib.load('models/categorical_mapping.pkl')
        scaler = joblib.load('models/scaler.pkl')
        st.success("✅ Modelo y artefactos cargados correctamente.")
        return model, categorical_mapping, scaler
    except FileNotFoundError as e:
        st.error(f"❌ Archivo no encontrado: {e}")
        return None, None, None
    except Exception as e:
        st.error(f"❌ Error al cargar modelo: {e}")
        return None, None, None

# ============================================================================== 
# 3. PREPROCESAMIENTO
# ==============================================================================

def preprocess_data(df, model_columns, categorical_mapping, scaler):
    df_processed = df.copy()

    for col in model_columns:
        if col not in df_processed.columns:
            df_processed[col] = np.nan

    numeric_cols = df_processed.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if not df_processed[col].isnull().all():
            df_processed[col] = df_processed[col].fillna(df_processed[col].mean())
        else:
            df_processed[col] = df_processed[col].fillna(0)

    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].astype(str).str.strip().str.upper()
            if col in categorical_mapping:
                try:
                    df_processed[col] = df_processed[col].map(categorical_mapping[col])
                except:
                    df_processed[col] = np.nan
            df_processed[col] = df_processed[col].fillna(-1)

    try:
        present_cols = [c for c in model_columns if c in df_processed.columns]
        df_to_scale = df_processed[present_cols].copy()
        if scaler is None:
            st.error("⚠️ No hay scaler disponible.")
            return None
        df_processed[present_cols] = scaler.transform(df_to_scale)
    except Exception as e:
        st.error(f"⚠️ Error al escalar datos: {e}")
        return None

    return df_processed[model_columns]


# ============================================================================== 
# 4. PREDICCIÓN Y RECOMENDACIONES
# ==============================================================================

def generar_recomendacion_personalizada(row):
    recomendaciones = []
    
    if row.get('IntencionPermanencia', 3) <= 2:
        recomendaciones.append("Reforzar desarrollo profesional.")
        
    if row.get('CargaLaboralPercibida', 3) >= 4:
        recomendaciones.append("Revisar carga laboral.")
        
    if row.get('SatisfaccionSalarial', 3) <= 2:
        recomendaciones.append("Evaluar ajustes salariales.")
        
    if row.get('ConfianzaEmpresa', 3) <= 2:
        recomendaciones.append("Fomentar confianza.")
        
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1:
        recomendaciones.append("Analizar ausentismo.")
        
    if row.get('PerformanceRating', 3) == 1:
        recomendaciones.append("Plan de mejora de desempeño.")

    return " | ".join(recomendaciones) if recomendaciones else "Sin alertas."

def run_prediction_pipeline(df_raw, model, categorical_mapping, scaler):
    df_original = df_raw.copy()
    df_input = df_original.drop(columns=['Attrition'], errors='ignore')

    processed = preprocess_data(df_input, MODEL_COLUMNS, categorical_mapping, scaler)
    if processed is None:
        return None

    try:
        prob = model.predict_proba(processed)[:, 1]
    except Exception as e:
        st.error(f"⚠️ Error en predicción: {e}")
        return None
    
    df_original['Probabilidad_Renuncia'] = prob
    df_original['Prediction_Renuncia'] = (prob > 0.5).astype(int)
    df_original['Recomendacion'] = df_original.apply(generar_recomendacion_personalizada, axis=1)
    
    return df_original


# ============================================================================== 
# 5. SUPABASE
# ==============================================================================

@st.cache_data(ttl=600)
def fetch_data_from_supabase(supabase_client: Client):
    if not SUPABASE_INSTALLED or supabase_client is None:
        st.error("❌ Cliente Supabase inválido.")
        return None
        
    try:
        result = supabase_client.table('consolidado').select('*').execute()
        data = getattr(result, 'data', None)
        if not data:
            st.warning("⚠️ Tabla vacía.")
            return None
            
        df = pd.DataFrame(data)
        return df

    except Exception as e:
        st.error(f"Error Supabase: {e}")
        return None

# ============================================================================== 
# 6. FUNCIÓN PRINCIPAL
# ==============================================================================

def predict_employee_data(df: pd.DataFrame = None, source: str = 'file', supabase_client: Optional[Client] = None):
    model, categorical_mapping, scaler = load_model_artefacts()
    if not model:
        return pd.DataFrame()

    if source == 'file' and df is None:
        st.error("⚠️ Debes subir un archivo antes de ejecutar la predicción.")
        return pd.DataFrame()

    if source == 'supabase':
        if supabase_client is None:
            st.error("⚠️ Cliente Supabase no válido.")
            return pd.DataFrame()
        df_raw = fetch_data_from_supabase(supabase_client)
        if df_raw is None:
            return pd.DataFrame()
    else:
        df_raw = df.copy()

    return run_prediction_pipeline(df_raw, model, categorical_mapping, scaler)


# ============================================================================== 
# 8. STREAMLIT
# ==============================================================================

if __name__ == '__main__':
    st.set_page_config(page_title="Módulo de Predicción de Renuncia", layout="wide")
    st.markdown("<h1 style='text-align:center;'>📦 Módulo de Predicción de Renuncia</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    SUPABASE_CLIENT = None
    
    if SUPABASE_INSTALLED:
        @st.cache_resource
        def get_supabase():
            try:
                url = st.secrets.get("SUPABASE_URL")
                key = st.secrets.get("SUPABASE_KEY")
                if not url or not key:
                    st.error("❌ Falta configuración de Supabase.")
                    return None
                return create_client(url, key)
            except Exception as e:
                st.error(f"Error Supabase: {e}")
                return None

        SUPABASE_CLIENT = get_supabase()

    if 'df_resultados' not in st.session_state:
        st.session_state.df_resultados = pd.DataFrame()

    tab1, tab2 = st.tabs(["📂 Predicción desde archivo", "☁️ Predicción desde Supabase"])

    # --------------------------------------------------------------------------
    # TAB 1 — ARCHIVO
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("📁 Cargar archivo")
        df_input = None

        uploaded_file = st.file_uploader("Sube un archivo CSV o Excel", type=["csv", "xlsx"])

        if uploaded_file:
            try:
                df_input = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                st.success(f"Archivo cargado correctamente ({len(df_input)} registros).")
                st.dataframe(df_input, use_container_width=True)
            except Exception as e:
                st.error(f"Error al leer archivo: {e}")
                df_input = None

        if st.button("🚀 Ejecutar Predicción desde Archivo", use_container_width=True):
            if df_input is None:
                st.error("⚠️ Debes subir un archivo antes de ejecutar.")
            else:
                with st.spinner("Procesando..."):
                    st.session_state.df_resultados = predict_employee_data(df=df_input, source='file')
                    st.success("Predicción completada.")

     --------------------------------------------------------------------------
    # TAB 2 — SUPABASE
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("☁️ Obtener datos desde Supabase")
        
        if st.button("🔄 Ejecutar Predicción desde Supabase", use_container_width=True):
            if SUPABASE_CLIENT is None:
                st.error("⚠️ Cliente Supabase no válido.")
            else:
                with st.spinner("Conectando..."):
                    st.session_state.df_resultados = predict_employee_data(source='supabase', supabase_client=SUPABASE_CLIENT)
                    st.success("Predicción completada desde Supabase.")

    st.markdown("---")

    # Mostrar resultados
    display_results_and_demo(st.session_state.df_resultados)


