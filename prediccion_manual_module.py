import pandas as pd
import numpy as np
import joblib
from xgboost import XGBClassifier
import streamlit as st
from typing import Dict, Any, List
import os
import warnings
warnings.filterwarnings("ignore") 

# ====================================================================
# CONFIGURACIÓN DEL MODELO Y ARTEFACTOS (AJUSTADO PARA LABEL ENCODING)
# ====================================================================

# RUTAS DE TUS ARCHIVOS
MODEL_PATH = 'xgboost_model.pkl' 
SCALER_PATH = 'scaler.pkl' 
MAPPING_PATH = 'categorical_mapping.pkl' # <-- RUTA AÑADIDA

# **IMPORTANTE:** MODEL_COLUMNS debe contener los nombres originales de las columnas
# categóricas, ya que serán transformadas por el mapeo numérico (Label Encoding)
MODEL_COLUMNS = [
    'Age', 'DailyRate', 'DistanceFromHome', 'Education', 'EnvironmentSatisfaction',
    'JobInvolvement', 'JobLevel', 'MonthlyIncome', 'NumCompaniesWorked', 
    'PerformanceRating', 'TotalWorkingYears', 'YearsAtCompany', 'YearsInCurrentRole', 
    'YearsSinceLastPromotion', 'YearsWithCurrManager', 
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato' # <-- Columnas categóricas incluidas aquí
]

# Las columnas categóricas a mapear
CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]

# Columnas numéricas/ordinales que deben ser escaladas
NUMERICAL_COLS_TO_SCALE = [
    'Age', 'DailyRate', 'DistanceFromHome', 'Education', 'EnvironmentSatisfaction',
    'JobInvolvement', 'JobLevel', 'MonthlyIncome', 'NumCompaniesWorked', 
    'PerformanceRating', 'TotalWorkingYears', 'YearsAtCompany', 'YearsInCurrentRole', 
    'YearsSinceLastPromotion', 'YearsWithCurrManager'
]

# Valores por defecto (ajustados para reflejar las columnas que se piden en la UI)
DEFAULT_MODEL_INPUTS = {
    'DailyRate': 800, 'Education': 3, 'EnvironmentSatisfaction': 3, 'JobInvolvement': 3, 
    'PerformanceRating': 3, 'YearsSinceLastPromotion': 1, 'YearsWithCurrManager': 4,
    'EducationField': 'LIFE_SCIENCES', # Ejemplo de valor por defecto
    'Gender': 'MALE', 
    'MaritalStatus': 'MARRIED',
    'BusinessTravel': 'TRAVEL_RARELY'
}

# Columnas para el What-If
WHAT_IF_VARIABLES = {
    "MonthlyIncome": "Ingreso Mensual",
    "TotalWorkingYears": "Años Totales Trabajados",
    "YearsAtCompany": "Años en la Compañía",
    "JobLevel": "Nivel de Puesto (1-5)",
    "OverTime": "¿Hace Horas Extra? (Sí/No)"
}

# ====================================================================
# FUNCIONES DE CARGA Y PREDICCIÓN (MODIFICADAS)
# ====================================================================

@st.cache_resource
def load_model_artefacts():
    """Carga el modelo, el escalador y el mapeo categórico."""
    model, scaler, mapping = None, None, None
    try:
        if os.path.exists(MODEL_PATH):
            model = joblib.load(MODEL_PATH) 
        else:
            st.error(f"❌ Modelo no encontrado en: {MODEL_PATH}")
        
        if os.path.exists(SCALER_PATH):
            scaler = joblib.load(SCALER_PATH)
        else:
            st.error(f"❌ Escalador no encontrado en: {SCALER_PATH}")

        # <-- CARGA DEL MAPPING AÑADIDA AQUÍ
        if os.path.exists(MAPPING_PATH):
            mapping = joblib.load(MAPPING_PATH)
        else:
            st.error(f"❌ Mapeo categórico no encontrado en: {MAPPING_PATH}")
        
        return model, scaler, mapping
    except Exception as e:
        st.error(f"Error CRÍTICO al cargar artefactos: {e}")
        return None, None, None

def preprocess_and_predict(input_data: Dict[str, Any], model, scaler, mapping) -> tuple:
    """Preprocesa el dict de entrada y realiza la predicción usando Label Encoding."""
    try:
        # 1. Crear DataFrame e inicializar
        df_input = pd.DataFrame([input_data])
        
        # 2. Aplicar Mapeo Categórico (Label Encoding)
        df_processed = df_input.copy()
        for col in CATEGORICAL_COLS_TO_MAP:
            if col in df_processed.columns and col in mapping:
                # Aplicar el mapeo numérico cargado
                df_processed[col] = df_processed[col].map(mapping[col])
                # Rellenar cualquier valor que no se mapeó (categoría desconocida) con NaN,
                # o el valor que usaste para desconocidos durante el entrenamiento. Aquí asumimos 
                # que no habrá desconocidos en el input manual.
                df_processed[col] = df_processed[col].fillna(df_processed[col].mode()[0] if not df_processed[col].empty else -1)
        
        # 3. Aplicar Escalado a las columnas numéricas
        df_scaled = df_processed.copy()
        
        # Asegurar que las columnas numéricas estén en el DataFrame (necesario para el escalador)
        for col in NUMERICAL_COLS_TO_SCALE:
            if col not in df_scaled.columns:
                df_scaled[col] = 0 # Rellenar con un valor si falta

        df_to_scale = df_scaled[NUMERICAL_COLS_TO_SCALE].copy()
        scaled_values = scaler.transform(df_to_scale)
        df_scaled.loc[:, NUMERICAL_COLS_TO_SCALE] = scaled_values
        
        # 4. Predicción
        final_input = df_scaled[MODEL_COLUMNS].astype(float)
        
        prediction_proba = model.predict_proba(final_input)[:, 1][0]
        predicted_class = 1 if prediction_proba >= 0.5 else 0
        
        return predicted_class, prediction_proba
        
    except Exception as e:
        st.error(f"Error durante el preprocesamiento o la predicción: {e}")
        return -1, 0.0

# ====================================================================
# FUNCIONES DE RECOMENDACIÓN Y WHAT-IF (NO NECESITAN CAMBIOS INTERNOS)
# ====================================================================

# (Las funciones generar_recomendacion y simular_what_if_individual no requieren cambios
# en su estructura, solo en cómo llaman a preprocess_and_predict)

def generar_recomendacion(prob_base: float, input_data: Dict[str, Any]) -> str:
    # ... (La lógica de recomendaciones sigue siendo la misma) ...
    recomendaciones = []
    
    if prob_base >= 0.7:
        recomendaciones.append("**Revisión Urgente:** El riesgo es extremadamente alto.")
    elif prob_base >= 0.5:
        recomendaciones.append("Riesgo moderado/alto. Intervención recomendada.")
        
    if input_data.get('MonthlyIncome', 5000) < 3000:
        recomendaciones.append("Evaluar compensación (Ingreso bajo).")
    if input_data.get('JobLevel', 2) == 1:
        recomendaciones.append("Fomentar planes de carrera (Nivel bajo).")
    if input_data.get('OverTime', 'NO') == 'YES': # Usar 'NO' y 'YES' para matching
        recomendaciones.append("Revisar carga y horas extra.")
    if input_data.get('YearsAtCompany', 3) >= 7 and input_data.get('YearsSinceLastPromotion', 1) >= 3:
         recomendaciones.append("Revisar promoción o reconocimiento (Antigüedad sin ascenso).")

    if not recomendaciones:
        return "Sin alertas específicas. El riesgo general es bajo."
        
    return " | ".join(recomendaciones)

def simular_what_if_individual(base_data: Dict[str, Any], variable_to_change: str, new_value: Any, model, scaler, mapping) -> float:
    """Ejecuta la predicción con un solo cambio para el análisis What-If."""
    df_input = base_data.copy()
    df_input[variable_to_change] = new_value
    
    # Se añade 'mapping' como argumento
    _, prob_what_if = preprocess_and_predict(df_input, model, scaler, mapping) 
    
    return prob_what_if

# ====================================================================
# FUNCIÓN DE RENDERIZADO (MODIFICADA)
# ====================================================================

def render_manual_prediction_tab():
    """Renderiza la interfaz completa de simulación y What-If en Streamlit."""
    
    model, scaler, mapping = load_model_artefacts() # <-- Carga el mapeo
    if model is None or scaler is None or mapping is None:
        st.warning("No se puede ejecutar la simulación. Verifique los logs de error.")
        return

    st.markdown("<h3 style='color:#1f77b4;'>Ingrese los Datos del Empleado para Predicción Base</h3>", unsafe_allow_html=True)
    
    # --- A. ENTRADA DE DATOS BASE (Formulario de Streamlit) ---
    user_input = DEFAULT_MODEL_INPUTS.copy()
    
    # Obtener las opciones para los selectbox del mapping
    job_role_options = list(mapping['JobRole'].keys())
    dept_options = list(mapping['Department'].keys())
    overtime_options = list(mapping['OverTime'].keys())
    contrato_options = list(mapping['tipo_contrato'].keys())
    
    col_input_1, col_input_2, col_input_3 = st.columns(3)
    
    # 1. Datos Personales y Puesto
    with col_input_1:
        st.subheader("Puesto y Demografía")
        user_input['Age'] = st.slider("Edad", 18, 60, 30, key='age_base')
        user_input['JobLevel'] = st.slider("Nivel de Puesto (1-5)", 1, 5, 2, key='joblevel_base')
        user_input['JobRole'] = st.selectbox("Puesto", job_role_options, key='jobrole_base')
        user_input['Department'] = st.selectbox("Departamento", dept_options, key='dept_base')

    # 2. Experiencia y Compensación
    with col_input_2:
        st.subheader("Compensación y Antigüedad")
        user_input['MonthlyIncome'] = st.number_input("Ingreso Mensual (S/.)", 1000, 25000, 5000, key='income_base')
        user_input['TotalWorkingYears'] = st.number_input("Años Totales Trabajados", 0, 40, 5, key='totalyears_base')
        user_input['YearsAtCompany'] = st.number_input("Años en la Compañía", 0, 40, 3, key='yearsatcomp_base')
        user_input['tipo_contrato'] = st.selectbox("Tipo de Contrato", contrato_options, key='contrato_base')
        
    # 3. Factores Físicos y Rol
    with col_input_3:
        st.subheader("Factores de Riesgo")
        user_input['DistanceFromHome'] = st.number_input("Distancia del Hogar (km)", 1, 30, 10, key='distance_base')
        user_input['OverTime'] = st.selectbox("¿Realiza Horas Extra?", overtime_options, key='overtime_base')
        user_input['YearsInCurrentRole'] = st.number_input("Años en el Rol Actual", 0, 18, 2, key='yearscurrent_base')
        
    # --- 2. PREDICCIÓN BASE Y RESULTADOS ---
    if st.button("🔮 Ejecutar Predicción Base", type="primary", use_container_width=True):
        
        st.session_state['base_input'] = user_input.copy()
        
        _, prob_base = preprocess_and_predict(user_input, model, scaler, mapping) # Pasa el mapping
        
        if prob_base != -1.0:
            st.session_state['prob_base'] = prob_base
            
            recomendacion = generar_recomendacion(prob_base, user_input)

            st.markdown(f"""
                <div style='background-color:#E3F2FD; padding:20px; border-radius:10px; text-align:center;'>
                    <h4>Resultado de Predicción BASE</h4>
                    <p style='font-size:24px;'>Probabilidad de renuncia: 
                    <b style='color:{"red" if prob_base>0.5 else "green"}'>{prob_base:.1%}</b></p>
                    <p><b>Recomendación:</b> {recomendacion}</p>
                </div>
            """, unsafe_allow_html=True)
    
    
    # ====================================================================
    # B. ANÁLISIS WHAT-IF
    # ====================================================================
    
    st.markdown("<hr/>")
    st.markdown("<h3 style='color:#1f77b4;'>💡 Análisis What-If (Simulación de Escenarios)</h3>", unsafe_allow_html=True)

    if 'prob_base' in st.session_state and 'base_input' in st.session_state:
        prob_base = st.session_state['prob_base']
        base_input = st.session_state['base_input']
        
        col_what_if_1, col_what_if_2 = st.columns(2)
        
        with col_what_if_1:
            variable_key = st.selectbox(
                "Selecciona la variable a modificar:",
                options=list(WHAT_IF_VARIABLES.keys()),
                format_func=lambda x: WHAT_IF_VARIABLES[x],
                key='whatif_var_select'
            )

        with col_what_if_2:
            variable_name = WHAT_IF_VARIABLES[variable_key]
            current_value = base_input.get(variable_key)
            
            # Lógica para inputs
            if variable_key == 'MonthlyIncome':
                new_value = st.number_input(f"Nuevo valor de {variable_name} (S/.)", 1000, 30000, int(current_value * 1.1), key='whatif_new_val')
            elif variable_key in ['TotalWorkingYears', 'YearsAtCompany']:
                new_value = st.number_input(f"Nuevo valor de {variable_name}", 0, 50, current_value + 1, key='whatif_new_val_num')
            elif variable_key == 'JobLevel':
                new_value = st.slider(f"Nuevo valor de {variable_name}", 1, 5, current_value + 1 if current_value < 5 else 5, key='whatif_new_val_level')
            elif variable_key == 'OverTime':
                index = overtime_options.index(current_value) 
                new_value = st.selectbox(f"Nuevo valor de {variable_name}", overtime_options, index=index, key='whatif_new_val_cat')
            else:
                 new_value = st.text_input(f"Nuevo valor de {variable_name}", str(current_value), key='whatif_new_val_text')
        
        if st.button("🚀 Ejecutar What-If", key='run_what_if', use_container_width=True):
            
            prob_what_if = simular_what_if_individual(
                base_data=base_input,
                variable_to_change=variable_key,
                new_value=new_value,
                model=model,
                scaler=scaler,
                mapping=mapping # Pasa el mapping
            )
            
            if prob_what_if != -1.0:
                cambio_pct = (prob_what_if - prob_base) / prob_base * 100 if prob_base > 0 else 0
                
                st.markdown("#### 🎯 Resultados de la Simulación")
                
                col_res_1, col_res_2 = st.columns(2)
                
                with col_res_1:
                    st.metric("Prob. Base", f"{prob_base:.1%}")
                    st.metric(
                        f"Prob. con {WHAT_IF_VARIABLES[variable_key]} = {new_value}", 
                        f"{prob_what_if:.1%}", 
                        delta=f"{cambio_pct:.1f}%",
                        delta_color="inverse"
                    )
                
                with col_res_2:
                    st.info(f"El cambio de **{WHAT_IF_VARIABLES[variable_key]}** a **{new_value}** resultó en un cambio del riesgo de renuncia de **{prob_base:.1%}** a **{prob_what_if:.1%}**.")
            
    else:
        st.warning("⚠️ Primero ejecuta la **Predicción Base** para habilitar el análisis What-If.")