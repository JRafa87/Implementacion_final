import pandas as pd
import numpy as np
import joblib
from xgboost import XGBClassifier
import streamlit as st
from typing import Dict, Any, List
import os
import warnings
from supabase import create_client, Client 

warnings.filterwarnings("ignore")

# ====================================================================
# 1. CONFIGURACIÓN DEL ENTORNO Y ARTEFACTOS (SIN CAMBIOS)
# ====================================================================

# RUTAS DE TUS ARCHIVOS (Asegúrate que existan)
MODEL_PATH = 'models/xgboost_model.pkl'
SCALER_PATH = 'models/scaler.pkl'
MAPPING_PATH = 'models/categorical_mapping.pkl'

# **MODEL_COLUMNS: 33 Características con ORDEN EXACTO ESPERADO**
MODEL_COLUMNS = [
    'Age', 'BusinessTravel', 'Department', 'DistanceFromHome', 'Education',
    'EducationField', 'EnvironmentSatisfaction', 'Gender', 'JobInvolvement',
    'JobLevel', 'JobRole', 'JobSatisfaction', 'MaritalStatus', 'MonthlyIncome',
    'NumCompaniesWorked', 'OverTime', 'PercentSalaryHike', 'PerformanceRating',
    'RelationshipSatisfaction', 'TotalWorkingYears', 'TrainingTimesLastYear',
    'WorkLifeBalance', 'YearsAtCompany', 'YearsInCurrentRole', 
    'YearsSinceLastPromotion', 'YearsWithCurrManager', 
    'IntencionPermanencia', 'CargaLaboralPercibida', 'SatisfaccionSalarial',
    'ConfianzaEmpresa', 'NumeroTardanzas', 'NumeroFaltas', 'tipo_contrato' 
]

# Columnas categóricas a mapear
CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]

# VALORES POR DEFECTO SINCRONIZADOS
DEFAULT_MODEL_INPUTS = {
    # Numéricas
    'Age': 30, 'DistanceFromHome': 10, 'Education': 3, 'JobInvolvement': 3, 
    'JobLevel': 2, 'MonthlyIncome': 5000, 'NumCompaniesWorked': 2, 
    'PercentSalaryHike': 12, 'PerformanceRating': 3, 'TotalWorkingYears': 10, 
    'TrainingTimesLastYear': 3, 'YearsAtCompany': 5, 'YearsInCurrentRole': 3,
    'YearsSinceLastPromotion': 1, 'YearsWithCurrManager': 3, 
    'NumeroTardanzas': 0, 'NumeroFaltas': 0,
    # Categóricas y de Satisfacción (1-4/1-5)
    'EnvironmentSatisfaction': 3, 'JobSatisfaction': 3, 'RelationshipSatisfaction': 3, 
    'WorkLifeBalance': 3, 'IntencionPermanencia': 3, 'CargaLaboralPercibida': 3, 
    'SatisfaccionSalarial': 3, 'ConfianzaEmpresa': 3,
    'EducationField': 'LIFE_SCIENCES', 'Gender': 'MALE', 
    'MaritalStatus': 'MARRIED', 'BusinessTravel': 'TRAVEL_RARELY', 
    'Department': 'RESEARCH_AND_DEVELOPMENT', 'JobRole': 'SALES_EXECUTIVE', 
    'OverTime': 'NO', 
    'tipo_contrato': 'PERMANENTE' 
}

# Columnas clave para la simulación What-If
WHAT_IF_VARIABLES = {
    "MonthlyIncome": "Ingreso Mensual",
    "TotalWorkingYears": "Años Totales Trabajados",
    "YearsAtCompany": "Años en la Compañía",
    "JobLevel": "Nivel de Puesto (1-5)",
    "OverTime": "¿Hace Horas Extra? (Sí/No)",
    "SatisfaccionSalarial": "Satisfacción Salarial (1-4)",
    "ConfianzaEmpresa": "Confianza en la Empresa (1-4)"
}

# ====================================================================
# 2. CONFIGURACIÓN DE SUPABASE (SIN CAMBIOS)
# ====================================================================

EMPLOYEE_TABLE = "consolidado"  # Tabla que contiene los datos
KEY_COLUMN = "EmployeeNumber"  # La columna de la BD para identificar al empleado
# ⚠️ AJUSTA ESTA COLUMNA: Nombre de la columna que indica la fecha de salida.
DATE_COLUMN = "FechaSalida" 

@st.cache_resource
def init_supabase_client():
    """Inicializa el cliente de Supabase usando st.secrets."""
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        
        if not url or not key:
            st.error("❌ ERROR: Faltan 'SUPABASE_URL' o 'SUPABASE_KEY' en tu archivo `.streamlit/secrets.toml`. No se puede conectar a la BD.")
            return None
            
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Error al inicializar Supabase: {e}")
        return None

# ====================================================================
# 3. FUNCIONES DE CARGA DE DATOS Y PREDICCIÓN (SIN CAMBIOS)
# ====================================================================

@st.cache_data(ttl=3600)
def fetch_employee_numbers() -> Dict[str, str]:
    # ... (Sin cambios)
    supabase: Client = init_supabase_client()
    if not supabase:
        return {}
        
    try:
        response = (
            supabase.table(EMPLOYEE_TABLE)
            .select(f"{KEY_COLUMN}")
            .is_(DATE_COLUMN, None)
            .execute()
        )
        
        employee_map = {
            str(row[KEY_COLUMN]): str(row[KEY_COLUMN])
            for row in response.data
        }
        return employee_map
    except Exception as e:
        st.error(f"Error al obtener la lista de empleados activos. Verifique las columnas ({KEY_COLUMN}, {DATE_COLUMN}): {e}")
        return {}

def load_employee_data(employee_number: str) -> Dict[str, Any] | None:
    # ... (Sin cambios)
    supabase: Client = init_supabase_client()
    if not supabase:
        return None

    try:
        response = supabase.table(EMPLOYEE_TABLE).select("*").eq(KEY_COLUMN, employee_number).limit(1).execute()
        
        if not response.data:
            st.warning(f"No se encontraron datos para {KEY_COLUMN}: {employee_number} en la tabla '{EMPLOYEE_TABLE}'.")
            return None
            
        employee_data_raw = response.data[0]
        
        input_for_model = {
            k: employee_data_raw.get(k, DEFAULT_MODEL_INPUTS.get(k)) 
            for k in MODEL_COLUMNS
        }
        return input_for_model

    except Exception as e:
        st.error(f"❌ Error CRÍTICO al consultar/procesar datos de Supabase: {e}")
        return None
        
# ====================================================================
# 4. FUNCIONES DE CARGA DEL MODELO (SIN CAMBIOS)
# ====================================================================

@st.cache_resource
def load_model_artefacts():
    # ... (Sin cambios)
    model, scaler, mapping = None, None, None
    try:
        model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
        scaler = joblib.load(SCALER_PATH) if os.path.exists(SCALER_PATH) else None
        mapping = joblib.load(MAPPING_PATH) if os.path.exists(MAPPING_PATH) else None

        if model is None: st.error(f"❌ Modelo no encontrado en: {MODEL_PATH}")
        if scaler is None: st.error(f"❌ Escalador no encontrado en: {SCALER_PATH}")
        if mapping is None: st.error(f"❌ Mapeo categórico no encontrado en: {MAPPING_PATH}")
        
        return model, scaler, mapping
    except Exception as e:
        st.error(f"Error CRÍTICO al cargar artefactos: {e}")
        return None, None, None

# ====================================================================
# 5. PREDICCIÓN Y SIMULACIÓN (SIN CAMBIOS)
# ====================================================================

def preprocess_and_predict(input_data: Dict[str, Any], model, scaler, mapping) -> tuple:
    # ... (Sin cambios)
    try:
        df_input = pd.DataFrame([input_data])
        final_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
        
        for col in MODEL_COLUMNS:
            val = df_input[col].iloc[0] if col in df_input.columns else DEFAULT_MODEL_INPUTS.get(col, 0)
            final_df[col] = val
        
        for col in CATEGORICAL_COLS_TO_MAP:
            if col in mapping:
                final_df[col] = final_df[col].map(mapping[col]).fillna(0)

        df_to_scale = final_df[MODEL_COLUMNS].copy()
        scaled_values = scaler.transform(df_to_scale)
        final_df.loc[:, MODEL_COLUMNS] = scaled_values
        
        final_input = final_df[MODEL_COLUMNS].astype(float)
        prediction_proba = model.predict_proba(final_input)[:, 1][0]
        predicted_class = 1 if prediction_proba >= 0.5 else 0
        
        return predicted_class, prediction_proba
        
    except Exception as e:
        st.error(f"Error durante el preprocesamiento y predicción: {e}")
        return -1, 0.0

# ====================================================================
# 6. FUNCIÓN DE RENDERIZADO (INTERFAZ Y LÓGICA SEPARADA)
# ====================================================================

def render_manual_prediction_tab():
    """Renderiza la interfaz completa de predicción base y simulación What-If."""
    
    st.set_page_config(layout="wide", page_title="Predicción de Renuncia")
    st.title("Sistema de Predicción de Riesgo de Renuncia 📉")

    model, scaler, mapping = load_model_artefacts()
    if model is None or scaler is None or mapping is None:
        return

    employee_map = fetch_employee_numbers() 
    
    # --- SECCIÓN 1: SELECCIÓN DE EMPLEADO Y PREDICCIÓN BASE ---
    st.header("1. Predicción Base (Datos Reales)")
    st.info("Selecciona un empleado para cargar sus datos y hacer una predicción sin modificaciones (ejecución independiente).")

    employee_options = ["--- Seleccionar un Empleado Activo ---"] + list(employee_map.keys())
    selected_id = st.selectbox(
        "Employee Number (ID):", 
        options=employee_options,
        key='base_id_selector'
    )
    
    # Inicializa el diccionario de inputs que se usará para la predicción
    prediction_inputs = None
    
    if selected_id != "--- Seleccionar un Empleado Activo ---":
        
        loaded_data = load_employee_data(selected_id)
        if loaded_data:
            # Los inputs de la predicción base son los datos cargados.
            prediction_inputs = loaded_data.copy()
            
            st.write(f"Datos cargados para el ID: **{selected_id}**")
            
            # Botón de Predicción Base
            if st.button(f"🔮 Predecir Riesgo Base (ID: {selected_id})", type="primary"):
                st.subheader("Resultado de la Predicción Base")
                
                predicted_class, prediction_proba = preprocess_and_predict(prediction_inputs, model, scaler, mapping)
                display_prediction_result(predicted_class, prediction_proba)
        else:
            st.warning("No se pudieron cargar datos específicos.")
    
    st.markdown("---")
    
    # --- SECCIÓN 2: SIMULACIÓN WHAT-IF (EJECUCIÓN INDEPENDIENTE) ---
    st.header("2. Simulación What-If (Manual)")
    st.info("Ajusta los parámetros para simular un escenario. Esto utiliza los valores por defecto o los últimos datos cargados como punto de partida.")

    # Usamos los datos por defecto como punto de partida para la simulación
    initial_inputs_for_what_if = prediction_inputs if prediction_inputs else DEFAULT_MODEL_INPUTS.copy()
    user_inputs = initial_inputs_for_what_if.copy()
    
    st.subheader("Ajustar Parámetros Clave para Simulación What-If")
    
    col_input_1, col_input_2 = st.columns(2)

    i = 0
    # Creamos los widgets de input para la simulación What-If
    for key, label in WHAT_IF_VARIABLES.items():
        
        col = col_input_1 if i % 2 == 0 else col_input_2
        current_val = initial_inputs_for_what_if.get(key, DEFAULT_MODEL_INPUTS.get(key))
        
        with col:
            # Manejar los tipos de entrada según la variable
            if key in ['MonthlyIncome', 'TotalWorkingYears', 'YearsAtCompany']:
                # Numéricos grandes
                user_inputs[key] = st.number_input(
                    label=f"{label}", 
                    value=int(current_val), 
                    min_value=0,
                    key=f'whatif_num_{key}'
                )
            elif key in ['JobLevel', 'SatisfaccionSalarial', 'ConfianzaEmpresa']:
                # Sliders de 1 a 5 o 1 a 4
                min_v = 1
                max_v = 5 if key == 'JobLevel' else 4
                user_inputs[key] = st.slider(
                    label=f"{label}",
                    min_value=min_v, 
                    max_value=max_v, 
                    value=int(current_val), 
                    key=f'whatif_slider_{key}'
                )
            elif key == 'OverTime':
                # Selectbox para categóricas binarias (OverTime)
                options = ['YES', 'NO']
                current_val_safe = current_val if current_val in options else 'NO'
                default_index = options.index(current_val_safe)
                
                user_inputs[key] = st.selectbox(
                    label=f"{label}", 
                    options=options, 
                    index=default_index,
                    key=f'whatif_cat_{key}'
                )
        i += 1
    
    # 4. Integración del What-If: Los datos finales para la simulación
    final_whatif_data = initial_inputs_for_what_if.copy()
    final_whatif_data.update(user_inputs) 
    
    st.markdown("---")
    
    # Botón de Predicción What-If
    if st.button("🔮 Ejecutar Predicción What-If", type="secondary", use_container_width=True):
        st.subheader("Resultado de la Simulación What-If")
        
        predicted_class, prediction_proba = preprocess_and_predict(final_whatif_data, model, scaler, mapping)
        display_prediction_result(predicted_class, prediction_proba)

# Función auxiliar para mostrar el resultado (para no repetir código)
def display_prediction_result(predicted_class: int, prediction_proba: float):
    """Muestra el resultado de la predicción con formato Streamlit."""
    if predicted_class == -1:
        st.error("No se pudo realizar la predicción debido a un error de preprocesamiento.")
        return

    risk_label = "ALTO RIESGO (Acción requerida)" if prediction_proba >= 0.5 else "Bajo a Moderado (Monitoreo)"
    st.metric(
        label="Probabilidad de Renuncia",
        value=f"{prediction_proba * 100:.2f}%",
        delta=risk_label,
        delta_color="inverse"
    )

    if predicted_class == 1:
        st.warning("🚨 **Riesgo ALTO:** Este empleado requiere atención inmediata.")
    else:
        st.success("✅ **Riesgo BAJO:** La probabilidad de renuncia es baja con los parámetros actuales.")


if __name__ == '__main__':
    render_manual_prediction_tab()
