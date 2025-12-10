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
# 1. CONFIGURACIÓN DEL ENTORNO Y ARTEFACTOS (RESTAURANDO VARIABLES NECESARIAS)
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
    'Age': 30, 'DistanceFromHome': 10, 'Education': 3, 'JobInvolvement': 3, 
    'JobLevel': 2, 'MonthlyIncome': 5000, 'NumCompaniesWorked': 2, 
    'PercentSalaryHike': 12, 'PerformanceRating': 3, 'TotalWorkingYears': 10, 
    'TrainingTimesLastYear': 3, 'YearsAtCompany': 5, 'YearsInCurrentRole': 3,
    'YearsSinceLastPromotion': 1, 'YearsWithCurrManager': 3, 
    'NumeroTardanzas': 0, 'NumeroFaltas': 0,
    'EnvironmentSatisfaction': 3, 'JobSatisfaction': 3, 'RelationshipSatisfaction': 3, 
    'WorkLifeBalance': 3, 'IntencionPermanencia': 3, 'CargaLaboralPercibida': 3, 
    'SatisfaccionSalarial': 3, 'ConfianzaEmpresa': 3,
    'EducationField': 'LIFE_SCIENCES', 'Gender': 'MALE', 
    'MaritalStatus': 'MARRIED', 'BusinessTravel': 'TRAVEL_RARELY', 
    'Department': 'RESEARCH_AND_DEVELOPMENT', 'JobRole': 'SALES_EXECUTIVE', 
    'OverTime': 'NO', 
    'tipo_contrato': 'PERMANENTE' 
}

# Columnas clave para la visualización/simulación manual (Paso 3)
ALL_DISPLAY_VARIABLES = {
    'Age': "Edad", 'Gender': "Género", 'Department': "Departamento",
    'JobRole': "Puesto de trabajo", 'MonthlyIncome': "Ingreso mensual (S./)", 
    'IntencionPermanencia': "Intención de permanencia (1-5)", 
    'CargaLaboralPercibida': "Carga laboral percibida (1-5)", 
    'SatisfaccionSalarial': "Satisfacción salarial (1-5)",
    'ConfianzaEmpresa': "Confianza en la empresa (1-5)",
    'NumeroTardanzas': "Número de tardanzas", 'NumeroFaltas': "Número de faltas",
    'BusinessTravel': "Frecuencia de viaje"
}

# Columnas clave para la Simulación Individual What-If (Paso 4)
WHAT_IF_VARIABLES = {
    "MonthlyIncome": "Ingreso Mensual",
    "TotalWorkingYears": "Años Totales Trabajados",
    "YearsAtCompany": "Años en la Compañía",
    "JobLevel": "Nivel de Puesto (1-5)",
    "OverTime": "¿Hace Horas Extra? (Sí/No)",
    "SatisfaccionSalarial": "Satisfacción Salarial (1-4)",
    "ConfianzaEmpresa": "Confianza en la Empresa (1-4)"
}

# Mapeo inverso de etiqueta a clave (para el selectbox del What-If Individual)
LABEL_TO_KEY = {v: k for k, v in WHAT_IF_VARIABLES.items()}

# Mapeo de opciones para Selectbox
SELECTBOX_OPTIONS = {
    'Gender': ['MALE', 'FEMALE'],
    'Department': ['RESEARCH_AND_DEVELOPMENT', 'SALES', 'HUMAN_RESOURCES'],
    'JobRole': ['SALES_EXECUTIVE', 'RESEARCH_SCIENTIST', 'LABORATORY_TECHNICIAN', 'MANUFACTURING_DIRECTOR', 'HEALTHCARE_REPRESENTATIVE', 'MANAGER', 'SALES_REPRESENTATIVE', 'RESEARCH_DIRECTOR', 'HUMAN_RESOURCES'],
    'BusinessTravel': ['TRAVEL_RARELY', 'TRAVEL_FREQUENTLY', 'NON_TRAVEL'],
    # Asegúrate de tener las opciones completas de tu dataset real
}

# ====================================================================
# 2. CONFIGURACIÓN DE SUPABASE Y FUNCIONES DE CARGA (SIN CAMBIOS)
# ====================================================================
EMPLOYEE_TABLE = "consolidado"
KEY_COLUMN = "EmployeeNumber"
DATE_COLUMN = "FechaSalida" 

@st.cache_resource
def init_supabase_client():
    # ... (Sin cambios)
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

@st.cache_data(ttl=3600)
def fetch_employee_numbers() -> Dict[str, str]:
    # ... (Sin cambios)
    supabase: Client = init_supabase_client()
    if not supabase: return {}
    try:
        response = (supabase.table(EMPLOYEE_TABLE).select(f"{KEY_COLUMN}").is_(DATE_COLUMN, None).execute())
        employee_map = {str(row[KEY_COLUMN]): str(row[KEY_COLUMN]) for row in response.data}
        return employee_map
    except Exception as e:
        st.error(f"Error al obtener la lista de empleados activos. Verifique las columnas ({KEY_COLUMN}, {DATE_COLUMN}): {e}")
        return {}

def load_employee_data(employee_number: str) -> Dict[str, Any] | None:
    # ... (Sin cambios)
    supabase: Client = init_supabase_client()
    if not supabase: return None
    try:
        response = supabase.table(EMPLOYEE_TABLE).select("*").eq(KEY_COLUMN, employee_number).limit(1).execute()
        if not response.data:
            st.warning(f"No se encontraron datos para {KEY_COLUMN}: {employee_number} en la tabla '{EMPLOYEE_TABLE}'.")
            return None
        employee_data_raw = response.data[0]
        input_for_model = {k: employee_data_raw.get(k, DEFAULT_MODEL_INPUTS.get(k)) for k in MODEL_COLUMNS}
        return input_for_model
    except Exception as e:
        st.error(f"❌ Error CRÍTICO al consultar/procesar datos de Supabase: {e}")
        return None
        
@st.cache_resource
def load_model_artefacts():
    # ... (Sin cambios en carga de artefactos)
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
# 3. PREDICCIÓN Y SIMULACIÓN (MANTENIENDO LÓGICA)
# ====================================================================

def preprocess_and_predict(input_data: Dict[str, Any], model, scaler, mapping) -> tuple:
    # ... (Función de preprocesamiento y predicción sin cambios)
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

def simular_what_if_individual(
    base_data: Dict[str, Any], 
    variable_to_change: str, 
    new_value: Any, 
    model: XGBClassifier, 
    scaler, 
    mapping
) -> float:
    """Modifica una sola variable en los datos base y ejecuta la predicción (Para Paso 4)."""
    simulated_data = base_data.copy()
    simulated_data[variable_to_change] = new_value
    _, prediction_proba = preprocess_and_predict(simulated_data, model, scaler, mapping)
    return prediction_proba

# Función auxiliar para mostrar el resultado (ESTRUCTURA DE DOS COLUMNAS - SIN CAMBIOS)
def display_prediction_result(predicted_class: int, prediction_proba: float, title: str):
    """Muestra el resultado de la predicción con el formato de métricas deseado."""
    
    st.markdown(f"#### {title}")
    
    if predicted_class == -1:
        st.error("No se pudo realizar la predicción debido a un error de preprocesamiento.")
        return

    risk_label = "ALTO RIESGO (Acción requerida)" if prediction_proba >= 0.5 else "Bajo a Moderado (Monitoreo)"
    
    col_metric, col_detail = st.columns([1, 2])

    with col_metric:
        st.metric(
            label="Probabilidad de Renuncia",
            value=f"{prediction_proba * 100:.2f}%",
            delta=risk_label,
            delta_color="inverse"
        )
    
    with col_detail:
        st.markdown("**Clase Predicha:**")
        if predicted_class == 1:
            st.warning(f"🚨 **Riesgo ALTO**")
        else:
            st.success(f"✅ **Riesgo BAJO**")
    
    st.markdown("---") 

# ====================================================================
# FUNCIÓN DE SIMULACIÓN MULTI-VARIABLE (Paso 3)
# ====================================================================

def display_simulation_widgets(data: Dict[str, Any]) -> Dict[str, Any]:
    """Muestra los datos del empleado en widgets EDITABLES y devuelve los valores modificados."""
    
    st.subheader("3. Simulación Multi-Variable (What-If: Múltiples variables)")
    st.info("Modifica los valores de las variables deseadas para crear un **Escenario Múltiple**.")
    
    user_inputs = data.copy()
    
    col_1, col_2 = st.columns(2)
    i = 0
    
    for key, label in ALL_DISPLAY_VARIABLES.items():
        if key not in data: continue 
        
        col = col_1 if i % 2 == 0 else col_2
        current_val = data.get(key)
        
        with col:
            # Lógica para crear los widgets EDITABLES
            if key in ['Age', 'MonthlyIncome', 'NumeroTardanzas', 'NumeroFaltas']:
                user_inputs[key] = st.number_input(label=label, value=int(current_val), min_value=0, key=f'sim_num_{key}')
            elif key in ['IntencionPermanencia', 'CargaLaboralPercibida', 'SatisfaccionSalarial', 'ConfianzaEmpresa']:
                min_v = 1
                max_v = 5 if key in ['IntencionPermanencia', 'CargaLaboralPercibida', 'SatisfaccionSalarial'] else 4 
                user_inputs[key] = st.slider(label=label, min_value=min_v, max_value=max_v, value=int(current_val), key=f'sim_slider_{key}')
            elif key in ['Gender', 'Department', 'JobRole', 'BusinessTravel']:
                options = SELECTBOX_OPTIONS.get(key, [current_val])
                try:
                    default_index = options.index(current_val)
                except ValueError:
                    default_index = 0
                
                user_inputs[key] = st.selectbox(label=label, options=options, index=default_index, key=f'sim_cat_{key}')
        i += 1
        
    st.markdown("---")
    return user_inputs

# ====================================================================
# 6. FUNCIÓN DE RENDERIZADO (LÓGICA PRINCIPAL CON AMBAS SIMULACIONES)
# ====================================================================

def render_manual_prediction_tab():
    """Renderiza la interfaz completa de predicción base y ambas simulaciones What-If."""
    
    st.set_page_config(layout="wide", page_title="Predicción de Renuncia")
    st.title("Sistema de Predicción de Riesgo de Renuncia 📉")

    model, scaler, mapping = load_model_artefacts()
    if model is None or scaler is None or mapping is None:
        return

    employee_map = fetch_employee_numbers() 
    
    # 1. INICIALIZAR SESSION STATE
    if 'prob_base' not in st.session_state:
        st.session_state['prob_base'] = 0.0
    if 'base_input' not in st.session_state:
        st.session_state['base_input'] = DEFAULT_MODEL_INPUTS.copy()
    if 'base_predicted' not in st.session_state:
        st.session_state['base_predicted'] = False


    # --- SECCIÓN 1: SELECCIÓN DE EMPLEADO BASE ---
    st.header("1. Selecciona el Empleado y sus Datos Base")

    current_selected_id = st.session_state.get('base_id_selector')
    
    employee_options = ["--- Seleccionar un Empleado Activo ---"] + list(employee_map.keys())
    selected_id = st.selectbox(
        "Employee Number (ID):", 
        options=employee_options,
        key='base_id_selector'
    )
    
    # Si el ID cambia, reseteamos el estado de predicción
    if selected_id != current_selected_id:
        st.session_state['base_predicted'] = False
        st.session_state['prob_base'] = 0.0
    
    # Lógica de carga de datos
    if selected_id != "--- Seleccionar un Empleado Activo ---":
        loaded_data = load_employee_data(selected_id)
        if loaded_data:
            st.session_state['base_input'] = loaded_data.copy()
            st.success(f"Datos base cargados exitosamente para el ID: **{selected_id}**")
        else:
            st.warning("No se pudieron cargar datos específicos. Usando valores por defecto como base.")
            st.session_state['base_input'] = DEFAULT_MODEL_INPUTS.copy()
    else:
        st.warning("Selecciona un empleado para empezar. Usando valores por defecto.")
        st.session_state['base_input'] = DEFAULT_MODEL_INPUTS.copy()
    
    st.markdown("---") 

    # --- SECCIÓN 2: PREDICCIÓN ACTUAL (Botón 1) ---
    st.header("2. Predicción Actual (Datos Reales del Empleado)")
    
    disabled_button = (selected_id == "--- Seleccionar un Empleado Activo ---" and not employee_map)

    # 2.1 Botón para ejecutar la predicción base
    if st.button(f"🔮 Ejecutar Predicción con Datos Actuales (ID: {selected_id})", type="primary", use_container_width=True, disabled=disabled_button):
        
        predicted_class, prediction_proba = preprocess_and_predict(st.session_state['base_input'], model, scaler, mapping)
        
        st.session_state['prob_base'] = prediction_proba
        st.session_state['base_predicted'] = True 
        display_prediction_result(predicted_class, prediction_proba, "Resultado de la Predicción Actual")
        st.balloons()
        
    st.markdown("---")
        
    # --- VERIFICACIÓN DE ESTADO PARA SIMULACIONES ---
    if not st.session_state['base_predicted']:
        st.warning("⚠️ Debes ejecutar la Predicción Actual (Paso 2) antes de usar las Simulaciones What-If para establecer la Probabilidad Base.")
        return

    # --- SECCIÓN 3: SIMULACIÓN WHAT-IF MULTI-VARIABLE (Completa, con sliders editables) ---
    
    # 3.1 Mostrar y capturar los valores modificados
    simulated_data = display_simulation_widgets(st.session_state['base_input'])
    
    # 3.2 Botón de Ejecución What-If y Comparación
    if st.button("🚀 Ejecutar Simulación **Multi-Variable** y Comparar", key='run_what_if_multi', type="secondary", use_container_width=True):
        
        prob_what_if_multi = preprocess_and_predict(simulated_data, model, scaler, mapping)[1]
        
        if prob_what_if_multi != -1.0:
            prob_base = st.session_state['prob_base'] 
            cambio_pct = (prob_what_if_multi - prob_base) / prob_base * 100 if prob_base != 0 else 0
            
            st.markdown("#### 🎯 Resultados de la Simulación Multi-Variable")
            
            col_res_base, col_res_whatif = st.columns(2)
            
            with col_res_base:
                st.markdown("**Probabilidad Base**")
                st.metric("Prob. Actual", f"{prob_base:.1%}")

            with col_res_whatif:
                st.markdown("**Escenario Múltiple**")
                st.metric(
                    "Prob. Escenario Simulado", 
                    f"{prob_what_if_multi:.1%}", 
                    delta=f"{cambio_pct:.1f}% de cambio",
                    delta_color="inverse"
                )
            
            st.markdown("---")
            if cambio_pct > 0:
                st.warning(f"🚨 **Conclusión:** La simulación Múltiple ha **AUMENTADO** el riesgo de renuncia en **{cambio_pct:.1f}%**.")
            elif cambio_pct < 0:
                st.success(f"✅ **Conclusión:** La simulación Múltiple ha **REDUCIDO** el riesgo de renuncia en **{-cambio_pct:.1f}%**.")
            else:
                st.info("ℹ️ **Conclusión:** El escenario simulado no tuvo impacto significativo en el riesgo de renuncia.")
        
    st.markdown("---")
    
    # --- SECCIÓN 4: SIMULACIÓN WHAT-IF INDIVIDUAL (La original, solo una variable) ---
    st.header("4. Simulación What-If Individual (Impacto de una variable)")
    
    st.info(f"Probabilidad Base registrada: **{st.session_state['prob_base']:.1%}**. Modifica **una sola variable** para ver su impacto aislado.")
    
    col_var, col_val = st.columns(2)
    
    with col_var:
        # 4.1 Selector de la variable a modificar
        variable_label = st.selectbox(
            "Selecciona la variable a modificar:",
            options=list(WHAT_IF_VARIABLES.values()),
            key='whatif_individual_select'
        )
        variable_key = LABEL_TO_KEY[variable_label]
        
    with col_val:
        # 4.2 Widget de entrada (Nuevo Valor)
        current_val = st.session_state['base_input'].get(variable_key, DEFAULT_MODEL_INPUTS.get(variable_key))
        
        # Lógica para renderizar el widget correcto para el nuevo valor
        if variable_key in ['MonthlyIncome', 'TotalWorkingYears', 'YearsAtCompany']:
            new_value = st.number_input(label=f"Nuevo valor para {variable_label}", value=int(current_val), min_value=0, key='whatif_new_value_individual')
        elif variable_key in ['JobLevel', 'SatisfaccionSalarial', 'ConfianzaEmpresa']:
            min_v = 1
            max_v = 5 if variable_key == 'JobLevel' else 4
            new_value = st.slider(label=f"Nuevo valor para {variable_label}", min_value=min_v, max_value=max_v, value=int(current_val), key='whatif_new_value_individual_slider')
        elif variable_key == 'OverTime':
            options = ['YES', 'NO']
            current_val_safe = current_val if current_val in options else 'NO'
            default_index = options.index(current_val_safe)
            new_value = st.selectbox(label=f"Nuevo valor para {variable_label}", options=options, index=default_index, key='whatif_new_value_individual_cat')
        else:
            new_value = st.number_input(label=f"Nuevo valor para {variable_label}", value=float(current_val), key='whatif_new_value_individual_other')

    st.markdown("---")
    
    # 4.3 Botón de Ejecución What-If Individual con lógica de comparación
    if st.button("🚀 Ejecutar Simulación **Individual** y Comparar", key='run_what_if_individual', type="secondary", use_container_width=True):
        
        prob_what_if_individual = simular_what_if_individual(
            base_data=st.session_state['base_input'],
            variable_to_change=variable_key,
            new_value=new_value,
            model=model,
            scaler=scaler,
            mapping=mapping 
        )
        
        if prob_what_if_individual != -1.0:
            prob_base = st.session_state['prob_base'] 
            cambio_pct = (prob_what_if_individual - prob_base) / prob_base * 100 if prob_base != 0 else 0
            
            st.markdown("#### 🎯 Resultados de la Simulación Individual")
            
            col_res_base, col_res_whatif = st.columns(2)
            
            # Columna de Resultado Base 
            with col_res_base:
                st.markdown("**Predicción Actual (Base)**")
                st.metric("Probabilidad Base", f"{prob_base:.1%}")

            # Columna de Resultado What-If (Comparación y Delta)
            with col_res_whatif:
                st.markdown("**Escenario Individual**")
                st.metric(
                    f"Prob. con {WHAT_IF_VARIABLES[variable_key]} = {new_value}", 
                    f"{prob_what_if_individual:.1%}", 
                    delta=f"{cambio_pct:.1f}% de cambio",
                    delta_color="inverse"
                )
            
            # Conclusión del Impacto
            st.markdown("---")
            if cambio_pct > 0:
                st.warning(f"🚨 **Conclusión:** El cambio de **{WHAT_IF_VARIABLES[variable_key]}** a **{new_value}** ha **AUMENTADO** el riesgo de renuncia en **{cambio_pct:.1f}%**.")
            elif cambio_pct < 0:
                st.success(f"✅ **Conclusión:** El cambio de **{WHAT_IF_VARIABLES[variable_key]}** a **{new_value}** ha **REDUCIDO** el riesgo de renuncia en **{-cambio_pct:.1f}%**.")
            else:
                st.info("ℹ️ **Conclusión:** El cambio no tuvo impacto significativo en el riesgo de renuncia.")


if __name__ == '__main__':
    render_manual_prediction_tab()