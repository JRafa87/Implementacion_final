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
        # Asegúrate de que estos archivos existan en la ruta 'models/'
        model = joblib.load('models/xgboost_model.pkl')
        categorical_mapping = joblib.load('models/categorical_mapping.pkl')
        scaler = joblib.load('models/scaler.pkl')
        st.success("✅ Modelo y artefactos cargados correctamente.")
        return model, categorical_mapping, scaler
    except FileNotFoundError as e:
        st.error(f"❌ Archivo no encontrado. Asegúrate de que el directorio 'models/' exista y contenga: 'xgboost_model.pkl', 'categorical_mapping.pkl' y 'scaler.pkl'. Error: {e}")
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
                    # Rellenar con NaN si el mapeo falla (por ejemplo, valor nuevo)
                    df_processed[col] = np.nan
            df_processed[col] = df_processed[col].fillna(-1) # Rellenar categorías no mapeadas

    try:
        present_cols = [c for c in model_columns if c in df_processed.columns]
        df_to_scale = df_processed[present_cols].copy()
        if scaler is None:
            st.error("⚠️ No hay scaler disponible.")
            return None
        # Solo escalar las columnas numéricas que realmente se escalaron durante el entrenamiento
        # (Esto es una simplificación, en un entorno real se usaría la lista de columnas numéricas del scaler)
        df_processed[present_cols] = scaler.transform(df_to_scale)
    except Exception as e:
        st.error(f"⚠️ Error al escalar datos: {e}")
        return None

    return df_processed[model_columns]


# ==============================================================================
# 4. PREDICCIÓN Y RECOMENDACIONES
# ==============================================================================

def generar_recomendacion_personalizada(row):
    """Genera recomendaciones basadas en las métricas blandas (soft) del empleado."""
    recomendaciones = []

    # Las variables blandas se asumen en una escala de 1 a 5, donde 1 es el peor y 5 es el mejor,
    # excepto Carga Laboral, donde 5 es la peor.
    
    # Intención de permanencia baja (1 o 2)
    if row.get('IntencionPermanencia', 3) <= 2:
        recomendaciones.append("Reforzar desarrollo profesional.")

    # Carga laboral percibida alta (4 o 5)
    if row.get('CargaLaboralPercibida', 3) >= 4:
        recomendaciones.append("Revisar carga laboral.")

    # Satisfacción salarial baja (1 o 2)
    if row.get('SatisfaccionSalarial', 3) <= 2:
        recomendaciones.append("Evaluar ajustes salariales.")

    # Confianza en la empresa baja (1 o 2)
    if row.get('ConfianzaEmpresa', 3) <= 2:
        recomendaciones.append("Fomentar confianza.")

    # Ausentismo alto
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1:
        recomendaciones.append("Analizar ausentismo.")

    # Rendimiento bajo (1, asumiendo una escala donde 1 es el más bajo)
    if row.get('PerformanceRating', 3) == 1:
        recomendaciones.append("Plan de mejora de desempeño.")

    return " | ".join(recomendaciones) if recomendaciones else "Sin alertas."

def run_prediction_pipeline(df_raw, model, categorical_mapping, scaler):
    df_original = df_raw.copy()
    # No dropear la columna 'Attrition' del raw data, sino antes de preprocess_data
    df_input = df_original.drop(columns=['Attrition'], errors='ignore')

    processed = preprocess_data(df_input, MODEL_COLUMNS, categorical_mapping, scaler)
    if processed is None:
        return None

    try:
        # Predicción de probabilidad de renuncia (clase 1)
        prob = model.predict_proba(processed)[:, 1]
    except Exception as e:
        st.error(f"⚠️ Error en predicción: {e}")
        return None

    df_original['Probabilidad_Renuncia'] = prob
    # 1 si Probabilidad > 0.5, 0 en otro caso
    df_original['Prediction_Renuncia'] = (prob > 0.5).astype(int)
    # Generar las recomendaciones
    df_original['Recomendacion'] = df_original.apply(generar_recomendacion_personalizada, axis=1)

    return df_original


# ==============================================================================
# 5. SUPABASE
# ==============================================================================

@st.cache_data(ttl=600)
def fetch_data_from_supabase(supabase_client: Client):
    if not SUPABASE_INSTALLED or supabase_client is None:
        st.error("❌ Cliente Supabase inválido. Asegúrate de tener 'supabase' instalado y las secrets configuradas.")
        return None

    try:
        # Reemplaza 'consolidado' con el nombre real de tu tabla si es diferente
        result = supabase_client.table('consolidado').select('*').execute()
        data = getattr(result, 'data', None)
        if not data:
            st.warning("⚠️ Tabla vacía o sin datos.")
            return None

        df = pd.DataFrame(data)
        # Convertir nombres de columnas a mayúsculas para un manejo más robusto
        df.columns = [col.capitalize() for col in df.columns]
        return df

    except Exception as e:
        st.error(f"Error Supabase: {e}")
        return None

# ==============================================================================
# 6. FUNCIÓN PRINCIPAL
# ==============================================================================

def predict_employee_data(df: pd.DataFrame = None, source: str = 'file', supabase_client: Optional[Client] = None):
    """Función principal para cargar el modelo y ejecutar la predicción."""
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
# 7. VISUALIZACIÓN DE RESULTADOS (FUNCIÓN FALTANTE)
# ==============================================================================

def display_results_and_demo(df_resultados: pd.DataFrame):
    """Muestra los resultados de la predicción, filtros y opciones de descarga."""
    if df_resultados.empty:
        st.info("💡 Esperando la ejecución de una predicción (archivo o Supabase) para mostrar resultados.")
        return

    st.markdown("<h2 style='text-align:center;'>📊 Resultados de la Predicción</h2>", unsafe_allow_html=True)
    st.markdown("---")

    # --- 7.1 Métricas Clave ---
    total_registros = len(df_resultados)
    renuncia_predicha = df_resultados['Prediction_Renuncia'].sum()
    tasa_predicha = (renuncia_predicha / total_registros) * 100 if total_registros > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Registros", f"{total_registros} empleados")
    col2.metric("Renuncia Predicha", f"{renuncia_predicha} empleados", delta=f"{tasa_predicha:.2f}% de la muestra")
    col3.metric("Promedio de Probabilidad", f"{df_resultados['Probabilidad_Renuncia'].mean():.2f}")

    # --- 7.2 Filtros y Gráfico ---
    st.subheader("Visualización y Análisis")
    
    col_chart, col_filter = st.columns([2, 1])

    # Filtros
    with col_filter:
        threshold = st.slider("Umbral de Probabilidad de Renuncia", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
        
        roles = df_resultados['JobRole'].unique().tolist() if 'JobRole' in df_resultados.columns else []
        selected_roles = st.multiselect("Filtrar por Rol de Trabajo", options=roles, default=roles)

        df_filtered = df_resultados[df_resultados['Probabilidad_Renuncia'] >= threshold]
        if 'JobRole' in df_filtered.columns:
             df_filtered = df_filtered[df_filtered['JobRole'].isin(selected_roles)]


    # Gráfico
    with col_chart:
        if 'Department' in df_filtered.columns:
            # Gráfico de barras de renuncia predicha por Departamento
            df_chart = df_filtered.groupby('Department')['Prediction_Renuncia'].sum().reset_index()
            df_chart.columns = ['Department', 'Renuncias_Predichas']
            
            fig = px.bar(
                df_chart,
                x='Department',
                y='Renuncias_Predichas',
                title='Renuncias Predichas por Departamento',
                color_discrete_sequence=px.colors.qualitative.Plotly,
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Columna 'Department' no encontrada en los datos de resultado.")

    st.subheader(f"Tabla de Resultados Filtrados ({len(df_filtered)} registros)")
    # --- 7.3 Tabla de Resultados ---
    st.dataframe(
        df_filtered[['JobRole', 'Department', 'MonthlyIncome', 'Probabilidad_Renuncia', 'Prediction_Renuncia', 'Recomendacion']].sort_values(
            'Probabilidad_Renuncia', ascending=False
        ),
        use_container_width=True,
        column_config={
            "Probabilidad_Renuncia": st.column_config.ProgressColumn(
                "Probabilidad de Renuncia",
                help="Probabilidad de que el empleado renuncie (Clase 1)",
                format="%.2f",
                min_value=0,
                max_value=1,
            ),
            "Prediction_Renuncia": st.column_config.TextColumn(
                "Predicción (1=Renuncia)",
                help="Clasificación binaria: 1 si Probabilidad > 0.5",
            ),
            "Recomendacion": st.column_config.TextColumn(
                "Recomendación Específica",
                help="Medidas sugeridas basadas en factores blandos de la encuesta",
                width="large",
            )
        }
    )

    # --- 7.4 Botones de Acción ---
    st.markdown("---")
    col_dl, col_demo = st.columns(2)

    # Botón de Descarga
    csv_download = df_filtered.to_csv(index=False).encode('utf-8')
    col_dl.download_button(
        label="📥 Descargar Resultados Filtrados (CSV)",
        data=csv_download,
        file_name=f'Predicciones_Renuncia_{datetime.now().strftime("%Y%m%d")}.csv',
        mime='text/csv',
        use_container_width=True
    )

    # Botón de Demostración (Simulado)
    # Este botón no hace nada funcionalmente en este código, es solo una demostración de un botón
    col_demo.button("🔍 Ver Dashboard Interactivo (Demo)", use_container_width=True, help="Simula la navegación a un dashboard de BI.")

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
                # Intenta obtener las secrets de Streamlit
                url = st.secrets.get("SUPABASE_URL")
                key = st.secrets.get("SUPABASE_KEY")
                if not url or not key:
                    st.error("❌ Falta configuración de Supabase. Asegúrate de tener 'SUPABASE_URL' y 'SUPABASE_KEY' en .streamlit/secrets.toml.")
                    return None
                return create_client(url, key)
            except Exception as e:
                st.error(f"Error al inicializar Supabase: {e}")
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
                # Determinar el tipo de archivo y leer
                if uploaded_file.name.endswith('.csv'):
                    df_input = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith('.xlsx'):
                    df_input = pd.read_excel(uploaded_file)
                else:
                    st.error("Formato de archivo no soportado.")
                    df_input = None

                if df_input is not None:
                    st.success(f"Archivo cargado correctamente ({len(df_input)} registros).")
                    st.dataframe(df_input.head(), use_container_width=True) # Mostrar solo el encabezado
            except Exception as e:
                st.error(f"Error al leer archivo: {e}")
                df_input = None

        if st.button("🚀 Ejecutar Predicción desde Archivo", key="btn_file_predict", use_container_width=True):
            if df_input is None:
                st.error("⚠️ Debes subir un archivo antes de ejecutar.")
            else:
                with st.spinner("Procesando la predicción..."):
                    st.session_state.df_resultados = predict_employee_data(df=df_input, source='file')
                    if not st.session_state.df_resultados.empty:
                        st.success("Predicción completada.")
                    else:
                         st.error("La predicción falló o devolvió resultados vacíos.")

    #--------------------------------------------------------------------------
    # TAB 2 — SUPABASE
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("☁️ Obtener datos desde Supabase")

        if st.button("🔄 Ejecutar Predicción desde Supabase", key="btn_supabase_predict", use_container_width=True):
            if SUPABASE_CLIENT is None:
                st.error("⚠️ Cliente Supabase no válido. Revisa tu configuración.")
            else:
                with st.spinner("Conectando y procesando..."):
                    st.session_state.df_resultados = predict_employee_data(source='supabase', supabase_client=SUPABASE_CLIENT)
                    if not st.session_state.df_resultados.empty:
                        st.success("Predicción completada desde Supabase.")
                    else:
                        st.error("La predicción falló o devolvió resultados vacíos. Revisa la conexión y la tabla 'consolidado'.")

    st.markdown("---")

    # Mostrar resultados (Esta es la llamada a la función que faltaba y se agregó arriba)
    display_results_and_demo(st.session_state.df_resultados)


