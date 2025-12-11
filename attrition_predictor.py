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

# **LISTA DE COLUMNAS REQUERIDAS POR EL MODELO (33 COLUMNAS)**
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
        st.error(f"❌ Archivo no encontrado. Error: {e}")
        return None, None, None
    except Exception as e:
        st.error(f"❌ Error al cargar modelo: {e}")
        return None, None, None

# ============================================================================== 
# 3. PREPROCESAMIENTO
# ==============================================================================

def preprocess_data(df, model_columns, categorical_mapping, scaler):
    df_processed = df.copy()

    # 1. Asegurar la presencia de todas las columnas requeridas
    for col in model_columns:
        if col not in df_processed.columns:
            df_processed[col] = np.nan

    # 2. Imputación de columnas numéricas existentes
    numeric_cols = df_processed.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if col in model_columns:
            if not df_processed[col].isnull().all():
                df_processed[col] = df_processed[col].fillna(df_processed[col].mean())
            else:
                df_processed[col] = df_processed[col].fillna(0) 

    # 3. Mapeo de columnas categóricas
    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].astype(str).str.strip().str.upper()
            if col in categorical_mapping:
                try:
                    df_processed[col] = df_processed[col].map(categorical_mapping[col])
                except:
                    df_processed[col] = np.nan
            df_processed[col] = df_processed[col].fillna(-1)
            df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce').fillna(-1) 

    # 4. CREAR EL DATAFRAME FINAL PARA EL ESCALADO (Asegurando orden y columnas)
    df_for_scaling = pd.DataFrame(index=df.index)
    
    for col in model_columns:
        if col in df_processed.columns:
            df_for_scaling[col] = pd.to_numeric(df_processed[col], errors='coerce')
        else:
            df_for_scaling[col] = 0.0

    df_for_scaling = df_for_scaling[model_columns] 
    df_for_scaling = df_for_scaling.fillna(df_for_scaling.mean(numeric_only=True))

    try:
        if scaler is None or df_for_scaling.empty:
            return None
            
        scaled_data = scaler.transform(df_for_scaling)
        df_scaled = pd.DataFrame(scaled_data, columns=model_columns, index=df.index)
        
        return df_scaled

    except Exception as e:
        st.error(f"⚠️ Error al escalar datos: {e}")
        return None


# ============================================================================== 
# 4. PREDICCIÓN Y RECOMENDACIONES (Lógica de Negocio)
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
    
    if processed is None or processed.empty:
         st.error("❌ La predicción no pudo continuar porque el preprocesamiento falló o devolvió un DataFrame vacío.")
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

@st.cache_resource
def init_supabase_client():
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None

def fetch_data_from_supabase(supabase_client: Client):
    if supabase_client is None:
        return None
    try:
        # Se elimina @st.cache_data para evitar UnhashableParamError y asegurar independencia
        result = supabase_client.table('consolidado').select('*').execute()
        data = getattr(result, 'data', None)
        if not data:
            return None
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error al obtener datos de Supabase: {e}") 
        return None


# ============================================================================== 
# 6. VISUALIZACIÓN FINAL (Formato Top 10)
# ==============================================================================

def display_results_and_demo(df_resultados: pd.DataFrame):
    """
    Muestra únicamente las métricas de alerta y la tabla del Top 10
    de empleados con mayor probabilidad de renuncia (formato solicitado).
    """
    if df_resultados.empty:
        st.info("💡 Ejecuta una predicción (desde archivo o Supabase) para ver los resultados.")
        return

    df = df_resultados.copy()
    
    st.markdown("<h2 style='text-align:center;'>📈 Dashboard de Riesgo de Rotación</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # --- 6.1 Métricas Clave y Alertas ---
    total_registros = len(df)
    
    col1, col2, col3 = st.columns(3)
    
    # Alerta de Riesgo 
    total_altos = (df["Probabilidad_Renuncia"] > 0.5).sum()
    
    with col2:
        if total_altos > 0:
            st.error(f"🔴 {total_altos} empleados ({total_altos/len(df):.1%}) con probabilidad > 50%.")
        else:
            st.success("🟢 Ningún empleado supera el 50% de probabilidad de renuncia.")

    col1.metric("Total de Registros", f"{total_registros} empleados")
    col3.metric("Promedio de Probabilidad", f"{df['Probabilidad_Renuncia'].mean():.2f}")
    
    st.markdown("---")
    
    # --- 6.2 Top 10 de Empleados ---
    st.subheader("👥 Top 10 empleados con mayor probabilidad de renuncia")
    df_top10 = df.sort_values('Probabilidad_Renuncia', ascending=False).head(10)

    def color_prob(val):
        """Devuelve el estilo HTML para colorear la probabilidad."""
        if val >= 0.5:
            return 'background-color:#FFCDD2; color:black; font-weight:bold;'
        elif 0.4 <= val < 0.5:
            return 'background-color:#FFF59D; color:black;'
        else:
            return 'background-color:#C8E6C9; color:black;'

    # Encabezados de columna
    col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([1.2, 1.5, 1.8, 1.5, 1, 1])
    with col_h1: st.write("**ID**")
    with col_h2: st.write("**Departamento**")
    with col_h3: st.write("**Rol**")
    with col_h4: st.write("**Salario (S/.)**")
    with col_h5: st.write("**Riesgo**")
    with col_h6: st.write("**Acción**")
    st.markdown("---") 

    # Filas de la tabla (Top 10)
    for i, row in df_top10.iterrows():
        col1, col2, col3, col4, col5, col6 = st.columns([1.2, 1.5, 1.8, 1.5, 1, 1])
        
        with col1: st.write(f"**{row.get('EmployeeNumber', i+1)}**")
        with col2: st.write(row.get('Department', '-'))
        with col3: st.write(row.get('JobRole', '-'))
        with col4: st.write(f"S/. {row.get('MonthlyIncome', 0):,.2f}")
        with col5:
            st.markdown(f"<div style='{color_prob(row['Probabilidad_Renuncia'])}; text-align:center; border-radius:8px; padding:4px;'>{row['Probabilidad_Renuncia']:.1%}</div>", unsafe_allow_html=True)
        with col6:
            with st.popover("🔍 Ver"):
                st.markdown("### 🧭 Recomendaciones")
                recs_str = str(row.get("Recomendacion", "Sin datos | No aplica"))
                recs = [r.strip() for r in recs_str.split(" | ") if r.strip()]
                for rec in recs:
                    st.write(f"- {rec}")
    
    st.markdown("---")

    # --- 6.3 Botón de Descarga CSV ---
    csv_download = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar Resultados Completos (CSV)",
        data=csv_download,
        file_name=f'Predicciones_Renuncia_{datetime.now().strftime("%Y%m%d")}.csv',
        mime='text/csv',
        use_container_width=True
    )


# ============================================================================== 
# 7. FUNCIÓN DE RENDERIZADO PARA LA PREDICCIÓN (render_predictor_page)
# ==============================================================================

def render_predictor_page():
    """
    Función principal de UI que renderiza el módulo de predicción
    y contiene las pestañas de Archivo y Supabase.
    """
    st.markdown("<h1 style='text-align:center;'>📦 Módulo de Predicción de Renuncia</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # --- Carga de Modelo (Prerrequisito) ---
    model, categorical_mapping, scaler = load_model_artefacts()
    if not model:
        return
    
    # --- Inicialización del Cliente Supabase ---
    SUPABASE_CLIENT = None
    supabase_ready = False
    if SUPABASE_INSTALLED:
        SUPABASE_CLIENT = init_supabase_client()
        if SUPABASE_CLIENT is None:
            st.warning("⚠️ No se pudo inicializar Supabase.")
        else:
            supabase_ready = True

    # --- Inicialización de Session State ---
    if 'df_resultados' not in st.session_state:
        st.session_state.df_resultados = pd.DataFrame()


    tab1, tab2 = st.tabs(["📂 Predicción desde archivo", "☁️ Predicción desde Supabase"])

    # --------------------------------------------------------------------------
    # TAB 1 — ARCHIVO (Actualización de resultados independiente)
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("📁 Cargar archivo")
        uploaded_file = st.file_uploader("Sube un archivo CSV o Excel", type=["csv", "xlsx"], key="file_upload_module_key")
        
        df_raw = None
        
        if uploaded_file is not None:
            try:
                uploaded_file.seek(0)
                df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                st.success(f"Archivo cargado correctamente ({len(df_raw)} registros).")
                st.dataframe(df_raw.head(), use_container_width=True)
            except Exception as e:
                st.error(f"Error al leer archivo: {e}")
                df_raw = None
        
        if df_raw is not None:
            if st.button("🚀 Ejecutar Predicción desde Archivo", key="btn_file_predict", use_container_width=True):
                with st.spinner("Procesando la predicción desde archivo..."):
                    df_predicho = run_prediction_pipeline(df_raw, model, categorical_mapping, scaler)
                    if df_predicho is not None and not df_predicho.empty:
                        # Solo actualiza la variable de estado si la predicción es exitosa
                        st.session_state.df_resultados = df_predicho
                        st.success("Predicción completada.")
                    else:
                        # Si falla, no actualiza el estado, pero el error ya se mostró
                        st.session_state.df_resultados = pd.DataFrame() 
                        st.error("❌ La predicción falló. Verifique el formato de las columnas de entrada.")
        else:
            st.info("Debes subir un archivo antes de ejecutar la predicción.")

    # --------------------------------------------------------------------------
    # TAB 2 — SUPABASE (Actualización de resultados independiente)
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("☁️ Obtener datos desde Supabase")
        
        if not supabase_ready:
             st.info("La conexión a Supabase no está lista. Verifica las claves en `secrets.toml`.")
        
        if st.button("🔄 Ejecutar Predicción desde Supabase", key="btn_supabase_predict", use_container_width=True, disabled=not supabase_ready):
            if SUPABASE_CLIENT is None:
                st.error("⚠️ Cliente Supabase no válido para la predicción.")
            else:
                with st.spinner("Conectando y procesando desde Supabase..."):
                    df_raw = fetch_data_from_supabase(SUPABASE_CLIENT)
                    
                    if df_raw is not None and not df_raw.empty:
                        st.dataframe(df_raw.head(), use_container_width=True) # Muestra el encabezado de los datos de Supabase
                        
                        df_predicho = run_prediction_pipeline(df_raw, model, categorical_mapping, scaler)
                        if df_predicho is not None and not df_predicho.empty:
                             # Solo actualiza la variable de estado si la predicción es exitosa
                            st.session_state.df_resultados = df_predicho
                            st.success("Predicción completada desde Supabase.")
                        else:
                            # Si falla, no actualiza el estado
                            st.session_state.df_resultados = pd.DataFrame()
                            st.error("❌ Fallo en el pipeline de predicción con datos de Supabase.")
                    else:
                        st.session_state.df_resultados = pd.DataFrame()
                        st.error("❌ No se pudieron cargar datos de Supabase.")

    st.markdown("---")

    # Mostrar la única sección de resultados (Alerta, Top 10 y CSV) con el mismo formato
    display_results_and_demo(st.session_state.df_resultados)

# ============================================================================== 
# 8. PUNTO DE ENTRADA (Para ejecución directa)
# ==============================================================================
if __name__ == '__main__':
    st.set_page_config(page_title="Módulo de Predicción de Renuncia", layout="wide")
    render_predictor_page()

