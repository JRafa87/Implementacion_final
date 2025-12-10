import pandas as pd
import numpy as np
import joblib
from xgboost import XGBClassifier
import streamlit as st
from typing import Dict, Any, List
import os
import warnings
from supabase import create_client, Client
from postgrest.base_request_builder import SingleAPIRequestBuilder 
# Importar is_ para filtros NULL: from postgrest import is_ (No es necesario importar, es parte de la librería Client)

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
# AJUSTA ESTA COLUMNA: Debe ser el nombre de la columna que registra la fecha de salida/attrition.
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
# 3. FUNCIONES DE CARGA DE DATOS Y PREDICCIÓN
# ====================================================================

@st.cache_data(ttl=3600)
def fetch_employee_numbers() -> Dict[str, str]:
    """
    Obtiene la lista de EmployeeNumber de empleados activos (sin fecha de salida).
    
    El filtro se aplica sobre DATE_COLUMN = NULL.
    Asume que 'nombre_completo' también está disponible para mejor UX.
    """
    supabase: Client = init_supabase_client()
    if not supabase:
        return {}
        
    try:
        # Selecciona el ID y el nombre, y filtra donde la columna de fecha de salida es nula (is.is_(None))
        response = (
            supabase.table(EMPLOYEE_TABLE)
            .select(f"{KEY_COLUMN}, nombre_completo")
            .is_(DATE_COLUMN, None) # <--- FILTRO CLAVE: Trae solo activos
            .execute()
        )
        
        # Mapea los resultados: EmployeeNumber -> nombre_completo (o ID como fallback)
        employee_map = {
            str(row[KEY_COLUMN]): row.get('nombre_completo', f"ID: {row[KEY_COLUMN]}") 
            for row in response.data
        }
        return employee_map
    except Exception as e:
        # Esto puede fallar si 'nombre_completo' o 'FechaSalida' no existen en la tabla
        st.error(f"Error al obtener la lista de empleados activos de Supabase. Verifique los nombres de las columnas ({KEY_COLUMN}, nombre_completo, {DATE_COLUMN}): {e}")
        return {}

def load_employee_data(employee_number: str) -> Dict[str, Any] | None:
    """Carga los datos reales del empleado desde Supabase (tabla 'consolidado')."""
    supabase: Client = init_supabase_client()
    if not supabase:
        return None

    try:
        response = supabase.table(EMPLOYEE_TABLE).select("*").eq(KEY_COLUMN, employee_number).limit(1).execute()
        
        if not response.data:
            st.warning(f"No se encontraron datos para {KEY_COLUMN}: {employee_number} en la tabla '{EMPLOYEE_TABLE}'.")
            return None
            
        employee_data_raw = response.data[0]
        
        # Mapeo de columnas de la BD a las 33 columnas del modelo
        input_for_model = {
            k: employee_data_raw.get(k, DEFAULT_MODEL_INPUTS.get(k)) 
            for k in MODEL_COLUMNS
        }
        return input_for_model

    except Exception as e:
        st.error(f"❌ Error CRÍTICO al consultar/procesar datos de Supabase: {e}")
        return None
# ====================================================================
# 4. FUNCIONES DE CARGA DEL MODELO (Sin Cambios)
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
# 5. PREDICCIÓN Y SIMULACIÓN (Sin Cambios)
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

    # 1. Cargar Employee Numbers (Solo Activos)
    employee_map = fetch_employee_numbers()
    
    # 2. Selector de Empleado
    st.subheader("Selecciona un empleado para precargar datos:")
    
    # Opciones que se muestran al usuario: Nombre (ID)
    display_options = {
        name: id_val for id_val, name in employee_map.items()
    }
    
    employee_options = ["(Ingreso Manual/Valores por Defecto)"] + list(display_options.keys())
    
    selected_name_or_default = st.selectbox(
        "Empleado Activo (sin fecha de salida):", 
        options=employee_options
    )
    
    # Obtener el ID seleccionado
    selected_id = display_options.get(selected_name_or_default, "(Ingreso Manual/Valores por Defecto)")
    
    # 3. Carga de Datos Base
    initial_inputs = DEFAULT_MODEL_INPUTS.copy()
    
    if selected_id != "(Ingreso Manual/Valores por Defecto)":
        loaded_data = load_employee_data(selected_id)
        if loaded_data:
            # Solo actualiza las claves que coinciden con MODEL_COLUMNS
            initial_inputs.update({k: v for k, v in loaded_data.items() if k in MODEL_COLUMNS})
            st.info(f"Datos precargados para: **{selected_name_or_default}** (ID: {selected_id})")
        else:
            st.warning("No se pudieron cargar datos específicos. Usando valores por defecto.")
    else:
        st.info("Usando valores por defecto para simulación manual.")
    
    
    st.markdown("---")
    st.subheader("Modificar Parámetros Clave para Predicción/What-If")
    
    # 4. Input de Parámetros (Usando initial_inputs como base)
    
    # Inicializa user_inputs con los valores base (cargados o por defecto)
    user_inputs = initial_inputs.copy()
    
    col_input_1, col_input_2 = st.columns(2)

    i = 0
    for key, label in WHAT_IF_VARIABLES.items():
        
        col = col_input_1 if i % 2 == 0 else col_input_2
        current_val = initial_inputs.get(key, DEFAULT_MODEL_INPUTS.get(key))
        
        with col:
            # Manejar los tipos de entrada según la variable para evitar errores de tipo en Streamlit
            if key in ['MonthlyIncome', 'TotalWorkingYears', 'YearsAtCompany']:
                # Numéricos grandes
                user_inputs[key] = st.number_input(
                    label=f"{label}", 
                    value=int(current_val), # Asegura que el valor sea int si se carga de BD
                    min_value=0,
                    key=f'input_num_{key}'
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
                    key=f'input_slider_{key}'
                )
            elif key == 'OverTime':
                # Selectbox para categóricas binarias (OverTime)
                options = ['YES', 'NO']
                default_index = options.index(current_val) if current_val in options else 1
                user_inputs[key] = st.selectbox(
                    label=f"{label}", 
                    options=options, 
                    index=default_index,
                    key=f'input_cat_{key}'
                )
        i += 1
    
    # Asegúrate de que TODAS las columnas que no están en WHAT_IF_VARIABLES mantengan su valor cargado/defecto
    final_input_data = initial_inputs.copy()
    final_input_data.update(user_inputs) # Sobreescribe solo las 7 variables del what-if
    
    st.markdown("---")
    
    # 5. Ejecutar Predicción
    if st.button("🔮 Predecir Riesgo de Renuncia", type="primary", use_container_width=True):
        
        predicted_class, prediction_proba = preprocess_and_predict(final_input_data, model, scaler, mapping)
        
        if predicted_class == -1:
            st.error("No se pudo realizar la predicción debido a un error de preprocesamiento.")
        else:
            st.markdown("### Resultado de la Predicción")
            
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
