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
        # NOTA: st.success se mueve fuera de cache_resource si bloquea, pero aquí se mantiene por simplicidad
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

    # Rellenar columnas faltantes en el input (deben estar en model_columns)
    for col in model_columns:
        if col not in df_processed.columns:
            df_processed[col] = np.nan

    # Imputación de columnas numéricas existentes
    numeric_cols = df_processed.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if not df_processed[col].isnull().all():
            df_processed[col] = df_processed[col].fillna(df_processed[col].mean())
        else:
            df_processed[col] = df_processed[col].fillna(0) # Si toda la columna es NaN

    # Mapeo de columnas categóricas
    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].astype(str).str.strip().str.upper()
            if col in categorical_mapping:
                try:
                    df_processed[col] = df_processed[col].map(categorical_mapping[col])
                except:
                    df_processed[col] = np.nan
            df_processed[col] = df_processed[col].fillna(-1) # Rellenar categorías no mapeadas
            
            # Asegurar que la columna mapeada es numérica para el escalado
            df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce').fillna(-1) 

    # Crear el DataFrame solo con las columnas del modelo para asegurar el orden
    df_for_scaling = pd.DataFrame(index=df.index)
    
    for col in model_columns:
        if col in df_processed.columns:
            # Asegurar que todas las columnas de entrada al scaler son numéricas
            df_for_scaling[col] = pd.to_numeric(df_processed[col], errors='coerce')
        else:
            df_for_scaling[col] = 0.0 # Rellenar columnas que faltaban y no se crearon antes

    # Rellenar cualquier NaN que quede después de la conversión a numérico
    df_for_scaling = df_for_scaling.fillna(df_for_scaling.mean(numeric_only=True))

    try:
        if scaler is None:
            st.error("⚠️ No hay scaler disponible.")
            return None
            
        if df_for_scaling.empty:
            st.error("⚠️ El DataFrame de entrada está vacío después del preprocesamiento inicial.")
            return None
            
        scaled_data = scaler.transform(df_for_scaling)
        df_scaled = pd.DataFrame(scaled_data, columns=model_columns, index=df.index)
        
        return df_scaled

    except Exception as e:
        st.error(f"⚠️ Error al escalar datos. Asegúrate de que las columnas coincidan con el scaler: {e}")
        return None


# ============================================================================== 
# 4. PREDICCIÓN Y RECOMENDACIONES
# ==============================================================================

def generar_recomendacion_personalizada(row):
    recomendaciones = []
    
    # Se asume una escala de 1 a 5 (Intención, Satisfacción, Confianza) donde 1 es el peor, 5 el mejor.
    # Carga laboral: 1 es el mejor, 5 es el peor.
    
    # Intención de permanencia baja
    if row.get('IntencionPermanencia', 3) <= 2:
        recomendaciones.append("Reforzar desarrollo profesional.")
        
    # Carga laboral percibida alta
    if row.get('CargaLaboralPercibida', 3) >= 4:
        recomendaciones.append("Revisar carga laboral.")
        
    # Satisfacción salarial baja
    if row.get('SatisfaccionSalarial', 3) <= 2:
        recomendaciones.append("Evaluar ajustes salariales.")
        
    # Confianza en la empresa baja
    if row.get('ConfianzaEmpresa', 3) <= 2:
        recomendaciones.append("Fomentar confianza.")
        
    # Ausentismo alto
    if row.get('NumeroTardanzas', 0) > 3 or row.get('NumeroFaltas', 0) > 1:
        recomendaciones.append("Analizar ausentismo.")
        
    # Rendimiento bajo
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
        st.error(f"⚠️ Error en predicción. El formato de las columnas preprocesadas no coincide con el modelo: {e}")
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
    """Inicializa y cachea el cliente Supabase, sin comandos de UI."""
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        
        # Si faltan las claves, devuelve None para manejar el error en el main
        if not url or not key:
            return None
            
        return create_client(url, key)
        
    except Exception:
        # Devuelve None si hay un error de inicialización
        return None

@st.cache_data(ttl=600)
def fetch_data_from_supabase(supabase_client: Client):
    if supabase_client is None:
        return None
        
    try:
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
            st.error("⚠️ Cliente Supabase no válido para la predicción.")
            return pd.DataFrame()
        df_raw = fetch_data_from_supabase(supabase_client)
        if df_raw is None:
            st.error("⚠️ No se pudieron cargar datos de Supabase.")
            return pd.DataFrame()
    else:
        df_raw = df.copy()

    return run_prediction_pipeline(df_raw, model, categorical_mapping, scaler)

# ============================================================================== 
# 7. VISUALIZACIÓN DE RESULTADOS
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

    with col_filter:
        threshold = st.slider("Umbral de Probabilidad de Renuncia", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
        
        roles = df_resultados['JobRole'].unique().tolist() if 'JobRole' in df_resultados.columns else []
        selected_roles = st.multiselect("Filtrar por Rol de Trabajo", options=roles, default=roles)

        df_filtered = df_resultados[df_resultados['Probabilidad_Renuncia'] >= threshold]
        if 'JobRole' in df_filtered.columns:
             df_filtered = df_filtered[df_filtered['JobRole'].isin(selected_roles)]


    with col_chart:
        if 'Department' in df_filtered.columns:
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

    csv_download = df_filtered.to_csv(index=False).encode('utf-8')
    col_dl.download_button(
        label="📥 Descargar Resultados Filtrados (CSV)",
        data=csv_download,
        file_name=f'Predicciones_Renuncia_{datetime.now().strftime("%Y%m%d")}.csv',
        mime='text/csv',
        use_container_width=True
    )

    col_demo.button("🔍 Ver Dashboard Interactivo (Demo)", key="btn_demo_dashboard", use_container_width=True, help="Simula la navegación a un dashboard de BI.")


# ============================================================================== 
# 8. STREAMLIT
# ==============================================================================

if __name__ == '__main__':
    st.set_page_config(page_title="Módulo de Predicción de Renuncia", layout="wide")
    st.markdown("<h1 style='text-align:center;'>📦 Módulo de Predicción de Renuncia</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # --- Inicialización del Cliente Supabase (Manejo de UI Separado) ---
    SUPABASE_CLIENT = None
    supabase_ready = False
    
    if SUPABASE_INSTALLED:
        SUPABASE_CLIENT = init_supabase_client()
        
        if SUPABASE_CLIENT is None:
            # Si el cliente falló, mostramos el error aquí, sin bloquear el renderizado de tabs
            st.warning("⚠️ No se pudo inicializar Supabase. La pestaña de BD estará deshabilitada o fallará si se intenta usar.")
        else:
            supabase_ready = True

    # --- Inicialización de Session State ---
    if 'df_resultados' not in st.session_state:
        st.session_state.df_resultados = pd.DataFrame()
    if 'df_entrada' not in st.session_state: # Agregado para persistir el DataFrame de Archivo
        st.session_state.df_entrada = pd.DataFrame()

    tab1, tab2 = st.tabs(["📂 Predicción desde archivo", "☁️ Predicción desde Supabase"])

    # --------------------------------------------------------------------------
    # TAB 1 — ARCHIVO (Corregido para usar st.session_state y persistir la carga)
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("📁 Cargar archivo")
        uploaded_file = st.file_uploader("Sube un archivo CSV o Excel", type=["csv", "xlsx"])

        # Lógica para leer el archivo y guardarlo en el estado
        if uploaded_file is not None:
            try:
                # Resetear la posición del puntero del archivo
                uploaded_file.seek(0)
                
                if uploaded_file.name.endswith('.csv'):
                    new_df_input = pd.read_csv(uploaded_file)
                else:
                    new_df_input = pd.read_excel(uploaded_file)
                
                st.session_state.df_entrada = new_df_input 
                
                st.success(f"Archivo cargado correctamente ({len(st.session_state.df_entrada)} registros).")
                st.dataframe(st.session_state.df_entrada.head(), use_container_width=True)
                
            except Exception as e:
                st.error(f"Error al leer archivo: {e}")
                st.session_state.df_entrada = pd.DataFrame()

        # Botón de ejecución, verifica el estado guardado
        if st.button("🚀 Ejecutar Predicción desde Archivo", key="btn_file_predict", use_container_width=True):
            if st.session_state.df_entrada.empty:
                st.error("⚠️ Debes subir un archivo válido antes de ejecutar.")
            else:
                with st.spinner("Procesando la predicción..."):
                    st.session_state.df_resultados = predict_employee_data(df=st.session_state.df_entrada, source='file')
                    if not st.session_state.df_resultados.empty:
                        st.success("Predicción completada.")
                    else:
                         st.error("❌ La predicción falló. Revisa los mensajes de error en el preprocesamiento o el modelo.")

    #--------------------------------------------------------------------------
    # TAB 2 — SUPABASE
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("☁️ Obtener datos desde Supabase")
        
        if not supabase_ready:
             st.info("La conexión a Supabase no está lista. Verifica las claves en `secrets.toml`.")
        
        if st.button("🔄 Ejecutar Predicción desde Supabase", key="btn_supabase_predict", use_container_width=True, disabled=not supabase_ready):
            if SUPABASE_CLIENT is None:
                st.error("⚠️ Cliente Supabase no válido. Revisa tu configuración.")
            else:
                with st.spinner("Conectando y procesando..."):
                    st.session_state.df_resultados = predict_employee_data(source='supabase', supabase_client=SUPABASE_CLIENT)
                    if not st.session_state.df_resultados.empty:
                        st.success("Predicción completada desde Supabase.")
                    else:
                        st.error("❌ La predicción falló al cargar datos de Supabase. Revisa la tabla 'consolidado'.")

    st.markdown("---")

    # Mostrar resultados
    display_results_and_demo(st.session_state.df_resultados)


