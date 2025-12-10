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
# 1. CONFIGURACIÓN DEL ENTORNO Y ARTEFACTOS
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
# 2. CONFIGURACIÓN DE SUPABASE (Adaptada a st.secrets)
# ====================================================================

EMPLOYEE_TABLE = "consolidado"  # Tabla que contiene los datos
KEY_COLUMN = "EmployeeNumber"  # La columna de la BD para identificar al empleado

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
# 3. FUNCIONES DE CARGA DE DATOS Y PREDICCIÓN
# ====================================================================

def fetch_employee_numbers() -> Dict[str, str]:
    """Obtiene la lista de EmployeeNumber desde Supabase."""
    supabase: Client = init_supabase_client()
    if not supabase:
        return {}
        
    try:
        # Asume que 'EmployeeNumber' es el único campo que se desea seleccionar en la tabla 'consolidado'
        response = supabase.table('consolidado').select(KEY_COLUMN).execute()
        
        # Mapea los resultados: EmployeeNumber -> EmployeeNumber
        employee_map = {str(row[KEY_COLUMN]): str(row[KEY_COLUMN]) for row in response.data}
        return employee_map
    except Exception as e:
        st.error(f"Error al obtener la lista de empleados de Supabase: {e}")
        return {}

# ====================================================================
# 4. FUNCIONES DE CARGA DEL MODELO
# ====================================================================

@st.cache_resource
def load_model_artefacts():
    """Carga el modelo, el escalador y el mapeo categórico."""
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
# 5. PREDICCIÓN Y SIMULACIÓN
# ====================================================================

def preprocess_and_predict(input_data: Dict[str, Any], model, scaler, mapping) -> tuple:
    """Preprocesa el dict de entrada y realiza la predicción."""
    try:
        df_input = pd.DataFrame([input_data])
        
        # Crear DataFrame con las 33 columnas del modelo
        final_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
        
        # Copiar valores de entrada al DataFrame final
        for col in MODEL_COLUMNS:
            val = df_input[col].iloc[0] if col in df_input.columns else DEFAULT_MODEL_INPUTS.get(col, 0)
            final_df[col] = val
        
        # Aplicar mapeo categórico (Label Encoding)
        for col in CATEGORICAL_COLS_TO_MAP:
            if col in mapping:
                final_df[col] = final_df[col].map(mapping[col])
                # Rellenar con 0 si la categoría no existe en el mapping
                final_df[col] = final_df[col].fillna(0)

        # Aplicar escalado a TODAS las 33 columnas
        df_to_scale = final_df[MODEL_COLUMNS].copy()
        scaled_values = scaler.transform(df_to_scale)
        final_df.loc[:, MODEL_COLUMNS] = scaled_values
        
        # Realizar la predicción
        final_input = final_df[MODEL_COLUMNS].astype(float)
        prediction_proba = model.predict_proba(final_input)[:, 1][0]
        predicted_class = 1 if prediction_proba >= 0.5 else 0
        
        return predicted_class, prediction_proba
        
    except Exception as e:
        st.error(f"Error durante el preprocesamiento y predicción: {e}")
        return -1, 0.0

# ====================================================================
# 6. FUNCIONES DE INTERFAZ Y SIMULACIÓN
# ====================================================================

def render_manual_prediction_tab():
    """Renderiza la interfaz completa de simulación y predicción de empleados."""
    
    st.set_page_config(layout="wide", page_title="Predicción de Renuncia")
    st.title("Sistema de Predicción de Riesgo de Renuncia 📉")

    model, scaler, mapping = load_model_artefacts()
    if model is None or scaler is None or mapping is None:
        return

    # Cargar Employee Numbers (Números de empleados)
    employee_map = fetch_employee_numbers()
    
    if employee_map:
        st.subheader("Selecciona un número de empleado:")
        employee_number = st.selectbox("Seleccionar Empleado", options=list(employee_map.keys()))
        if employee_number:
            st.write(f"Empleado seleccionado: {employee_map[employee_number]}")
            
            # Simulación con inputs de ejemplo o manuales
            user_inputs = {key: st.number_input(value=val, label=f"Valor de {value}") for key, value in WHAT_IF_VARIABLES.items()}
            if st.button("Predecir Riesgo"):
                predicted_class, prediction_proba = preprocess_and_predict(user_inputs, model, scaler, mapping)
                st.write(f"Resultado: {prediction_proba * 100:.2f}% probabilidad de renuncia." if predicted_class == 1 else "El riesgo de renuncia es bajo.")
