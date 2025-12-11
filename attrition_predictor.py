import pandas as pd
import numpy as np
import joblib
import streamlit as st
import plotly.express as px
from datetime import datetime
from typing import Optional


# ==============================================================================
# 1. CONSTANTES Y CONFIGURACIÓN (Se mantiene igual)
# ==============================================================================

# Columnas que deben entrar al modelo, en el orden correcto (33 variables)
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

# Columnas categóricas que necesitan mapeo numérico
CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]


# ==============================================================================
# 2. CARGA DE MODELO Y ARTEFACTOS (Se mantiene igual)
# ==============================================================================

@st.cache_resource
def load_model_artefacts():
    """Carga el modelo pre-entrenado, el mapeo de categóricas y el escalador."""
    try:
        model = joblib.load('models/xgboost_model.pkl')
        categorical_mapping = joblib.load('models/categorical_mapping.pkl')
        scaler = joblib.load('models/scaler.pkl')
        st.success("✅ Modelo y artefactos cargados correctamente.")
        return model, categorical_mapping, scaler
    except FileNotFoundError as e:
        st.error(f"❌ Error: Archivo de modelo no encontrado: {e}. Asegúrate de que los .pkl estén en la carpeta 'models/'.")
        return None, None, None
    except Exception as e:
        st.error(f"❌ Error al cargar modelo o artefactos: {e}")
        return None, None, None


# ==============================================================================
# 3. PREPROCESAMIENTO (Se mantiene igual)
# ==============================================================================

def preprocess_data(df, model_columns, categorical_mapping, scaler):
    """
    Prepara el DataFrame de entrada (df) para la predicción, aplicando
    imputación, codificación de categóricas y escalado.
    """
    df_processed = df.copy()

    # 1. Asegurar la presencia de todas las columnas del modelo
    for col in model_columns:
        if col not in df_processed.columns:
            df_processed[col] = np.nan

    # 2. Imputación Numérica (rellenar NaN con la media)
    numeric_cols = df_processed.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if col in df_processed.columns:
            if not df_processed[col].isnull().all():
                df_processed[col] = df_processed[col].fillna(df_processed[col].mean())
            else:
                df_processed[col] = df_processed[col].fillna(0) 

    # 3. Codificación Categórica
    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].astype(str).str.strip().str.upper()
            
            if col in categorical_mapping:
                df_processed[col] = df_processed[col].map(categorical_mapping[col])
            
            df_processed[col] = df_processed[col].fillna(-1)

    # 4. Escalado
    try:
        present_cols = [c for c in model_columns if c in df_processed.columns]
        df_to_scale = df_processed[present_cols].copy()
        df_processed[present_cols] = scaler.transform(df_to_scale)
    except Exception as e:
        st.error(f"⚠️ Error al escalar datos: {e}. El DataFrame podría no ser apto.")
        return None

    return df_processed[model_columns]


# ==============================================================================
# 4. GENERACIÓN DE RECOMENDACIONES Y PREDICCIÓN (Se mantiene igual)
# ==============================================================================

def generar_recomendacion_personalizada(row):
    """Genera recomendaciones basadas en umbrales lógicos de las columnas de encuesta/RRHH."""
    recomendaciones = []
    
    if row.get('IntencionPermanencia', 3) <= 2:
        recomendaciones.append("Reforzar desarrollo profesional (Baja intención de permanencia).")
        
    if row.get('CargaLaboralPercibida', 3) >= 4:
        recomendaciones.append("Revisar carga laboral (Percepción de alta sobrecarga).")
        
    if row.get('SatisfaccionSalarial', 3) <= 2:
        recomendaciones.append("Evaluar ajustes salariales (Baja satisfacción salarial).")
        
    if row.get('ConfianzaEmpresa', 3) <= 2:
        recomendaciones.append("Fomentar la confianza y comunicación (Baja confianza en la empresa).")
        
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1:
        recomendaciones.append("Analizar causas de ausentismo (Tardanzas/Faltas frecuentes).")
        
    if row.get('PerformanceRating', 3) == 1:
        recomendaciones.append("Plan de mejora de desempeño (Performance Rating bajo).")

    if not recomendaciones:
        recomendaciones.append("Sin alertas relevantes. Seguimiento preventivo.")
    
    return " | ".join(recomendaciones)


def run_prediction_pipeline(df_raw, model, categorical_mapping, scaler):
    """Ejecuta el preprocesamiento, la predicción y genera recomendaciones."""
    
    df_input = df_raw.drop(columns=['Attrition'], errors='ignore')

    processed = preprocess_data(df_input, MODEL_COLUMNS, categorical_mapping, scaler)
    
    if processed is None:
        return None

    # Predicción
    prob = model.predict_proba(processed)[:, 1]
    
    df_raw['Probabilidad_Renuncia'] = prob
    df_raw['Prediction_Renuncia'] = (prob > 0.5).astype(int)
    df_raw['Recomendacion'] = df_raw.apply(generar_recomendacion_personalizada, axis=1)
    
    return df_raw


# ==============================================================================
# 5. FUNCIONALIDAD SUPABASE (Usando la tabla 'consolidado')
# ==============================================================================

@st.cache_data(ttl=600)
def fetch_data_from_supabase(supabase_client: Client):
    """
    Consulta directamente la tabla 'consolidado' que contiene todos los datos.
    Se espera que esta tabla contenga las 33 variables de MODEL_COLUMNS.
    """
    if supabase_client is None:
        # Esta comprobación es redundante si el código está bien estructurado, pero es un buen guardrail
        st.error("❌ El cliente de Supabase no es válido. No se puede conectar.")
        return None
        
    st.info(f"Consultando Supabase. Obteniendo datos de la tabla 'consolidado' ({len(MODEL_COLUMNS)} variables esperadas)...")
    try:
        data = supabase_client.table('consolidado').select('*').execute().data
        
        if not data:
            st.warning("⚠️ La tabla 'consolidado' está vacía o la consulta no devolvió resultados.")
            return None
            
        df = pd.DataFrame(data)
        st.success(f"✅ {len(df)} registros obtenidos de 'consolidado'.")
        
        missing_cols = [col for col in MODEL_COLUMNS if col not in df.columns]
        if missing_cols:
            st.warning(f"⚠️ Atención: Faltan {len(missing_cols)} variables críticas del modelo en la tabla 'consolidado'. El preprocesamiento intentará imputarlas.")
        
        if 'EmployeeNumber' not in df.columns and 'id' in df.columns:
             df = df.rename(columns={'id': 'EmployeeNumber'})
             
        return df

    except Exception as e:
        st.error(f"Error al obtener datos de Supabase desde 'consolidado': {e}")
        return None

# ==============================================================================
# 6. FUNCIÓN PÚBLICA DEL MÓDULO
# ==============================================================================

def predict_employee_data(df: pd.DataFrame = None, source: str = 'file', supabase_client: Optional[Client] = None):
    """
    Función principal para ejecutar la predicción.
    
    Args:
        df (pd.DataFrame, opcional): DataFrame a predecir si source='file'.
        source (str): 'file' o 'supabase'.
        supabase_client (Client, opcional): Cliente autenticado de Supabase si source='supabase'.
        
    Returns:
        pd.DataFrame: DataFrame con las columnas de predicción y recomendación añadidas.
        
    """
    model, categorical_mapping, scaler = load_model_artefacts()
    if not model:
        return pd.DataFrame()
        
    df_raw = None
    
    if source == 'supabase':
        if supabase_client is None:
             st.error("Se seleccionó 'supabase', pero el cliente de Supabase no fue proporcionado o es nulo.")
             return pd.DataFrame()
             
        df_raw = fetch_data_from_supabase(supabase_client)
        
        if df_raw is None or df_raw.empty:
            st.error("No hay datos válidos para la predicción desde la base de datos.")
            return pd.DataFrame()
            
    elif source == 'file' and df is not None:
        df_raw = df.copy()
    else:
        st.error("Se requiere un DataFrame de entrada (source='file') o un cliente de Supabase válido (source='supabase').")
        return pd.DataFrame()
    
    st.info(f"Ejecutando predicción para {len(df_raw)} registros, utilizando las {len(MODEL_COLUMNS)} variables del modelo.")
    
    df_result = run_prediction_pipeline(df_raw, model, categorical_mapping, scaler)
    return df_result


# ==============================================================================
# 7. FUNCIONES DE EXPORTACIÓN Y DEMO (Se mantienen igual)
# ==============================================================================

@st.cache_data
def export_results_to_excel(df):
    from io import BytesIO
    output = BytesIO()
    df_export = df.rename(columns={
        'Probabilidad_Renuncia': 'Probabilidad (%)',
        'Prediction_Renuncia': 'Predicción (0/1)',
        'Recomendacion': 'Recomendación Estratégica'
    })
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, sheet_name='Predicciones', index=False)
    return output.getvalue()


def display_results_and_demo(df):
    if df is None or df.empty:
        return

    st.subheader("✅ Resultados de la Predicción")

    df['Probabilidad (%)'] = (df['Probabilidad_Renuncia'] * 100).round(1).astype(str) + '%'
    
    total_altos = (df["Probabilidad_Renuncia"] > 0.5).sum()
    if total_altos > 0:
        st.error(f"🔴 {total_altos} empleados ({total_altos/len(df):.1%}) con probabilidad > 50%.")
    else:
        st.success("🟢 Ningún empleado supera el 50% de probabilidad de renuncia.")

    
    st.subheader("👥 Top Empleados con Mayor Riesgo")
    
    id_col = 'EmployeeNumber' if 'EmployeeNumber' in df.columns else ('id' if 'id' in df.columns else None)
    
    columns_to_show = [id_col, 'Department', 'JobRole', 'MonthlyIncome', 
                       'Probabilidad (%)', 'Recomendacion']
    
    columns_to_show = [col for col in columns_to_show if col is not None]

    df_display = df.sort_values('Probabilidad_Renuncia', ascending=False).head(20)
    
    col_mapping = {
        id_col: 'ID Empleado',
        'Department': 'Departamento',
        'JobRole': 'Puesto',
        'MonthlyIncome': 'Salario Mensual',
        'Recomendacion': 'Recomendación Estratégica'
    }
    
    df_display = df_display[columns_to_show].rename(columns=col_mapping)
    
    def format_currency(val):
        return f"S/. {val:,.2f}" if isinstance(val, (int, float)) else val
    
    def style_probability(val):
        num_val = float(val.strip('%')) / 100
        if num_val >= 0.5:
            return 'background-color:#E57373; color:black; font-weight:bold;'
        elif 0.4 <= num_val < 0.5:
            return 'background-color:#FFF59D; color:black;'
        else:
            return 'background-color:#C8E6C9; color:black;'

    st.dataframe(
        df_display.style.applymap(style_probability, subset=['Probabilidad (%)'])
                       .format({'Salario Mensual': format_currency}),
        use_container_width=True,
        height=400
    )

    st.subheader("📊 Análisis General")
    if 'Department' in df.columns and not df['Department'].isnull().all():
        dept_avg = df.groupby('Department')['Probabilidad_Renuncia'].mean().reset_index()

        col1, col2 = st.columns([2, 1])
        with col1:
            fig_bar = px.bar(dept_avg, x='Department', y='Probabilidad_Renuncia',
                             color='Probabilidad_Renuncia', text_auto='.1%',
                             color_continuous_scale=['#8BC34A','#FFEB3B','#E57373'],
                             title="Probabilidad Promedio por Departamento")
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            st.markdown("##### 📥 Descargar Resultados Completos")
            excel_data = export_results_to_excel(df)
            st.download_button(
                label="⬇️ Descargar reporte Excel (Completo)",
                data=excel_data,
                file_name=f"reporte_predicciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.write("")
            st.info("El archivo incluye todas las columnas de entrada y los resultados.")
    else:
        st.warning("No hay datos válidos de 'Department' para generar el análisis gráfico.")


# ==============================================================================
# 8. DEMOSTRACIÓN DE STREAMLIT (Con Inicialización de Cliente)
# ==============================================================================

if __name__ == '__main__':
    st.set_page_config(page_title="Módulo de Predicción de Renuncia", layout="wide")
    st.markdown("<h1 style='text-align:center; color:#1f77b4;'>📦 Módulo de Predicción de Renuncia (Demo)</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # --- INICIALIZACIÓN DEL CLIENTE DE SUPABASE (Tu código) ---
    @st.cache_resource
    def init_supabase_client() -> Optional[Client]:
        """Inicializa y cachea el cliente de Supabase."""
        try:
            url = st.secrets.get("SUPABASE_URL")
            key = st.secrets.get("SUPABASE_KEY")
            if not url or not key:
                st.error("❌ ERROR: Faltan 'SUPABASE_URL' o 'SUPABASE_KEY' en tu archivo `.streamlit/secrets.toml`. No se puede conectar a la BD.")
                return None
            
            # Nota: create_client fue importado al inicio del script
            return create_client(url, key)
        except Exception as e:
            st.error(f"❌ Error al inicializar Supabase: {e}")
            return None

    SUPABASE_CLIENT = init_supabase_client()
    # -----------------------------------------------------------

    if 'df_resultados' not in st.session_state:
        st.session_state.df_resultados = pd.DataFrame()

    tab1, tab2 = st.tabs(["📂 Predicción desde archivo", "☁️ Predicción desde Supabase"])

    with tab1:
        df_input = None
        uploaded_file = st.file_uploader("Sube tu archivo CSV o Excel", type=["csv", "xlsx"])
        if uploaded_file:
            try:
                df_input = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                st.info(f"Archivo cargado: {len(df_input)} registros.")
            except Exception as e:
                st.error(f"Error al leer archivo: {e}")
                df_input = None
            
        if st.button("🚀 Ejecutar Predicción desde Archivo", use_container_width=True, key='predict_file'):
            with st.spinner('Procesando datos y generando predicciones...'):
                st.session_state.df_resultados = predict_employee_data(df=df_input, source='file')


    with tab2:
        st.markdown("Presiona para obtener los datos más recientes directamente de la tabla **`consolidado`**.")
        
        if SUPABASE_CLIENT is not None:
            if st.button("🔄 Ejecutar Predicción desde Supabase", use_container_width=True, key='predict_supabase'):
                with st.spinner('Conectando a Supabase y procesando datos...'):
                    # Pasa el cliente autenticado
                    st.session_state.df_resultados = predict_employee_data(source='supabase', supabase_client=SUPABASE_CLIENT)
        else:
            st.warning("⚠️ La opción de Supabase está deshabilitada. Revisa los errores de conexión de la BD arriba.")

    st.markdown("---")
    
    display_results_and_demo(st.session_state.df_resultados)