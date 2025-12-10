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
# CONFIGURACIÓN DEL MODELO Y ARTEFACTOS (33 FEATURES ESCALADAS)
# ====================================================================

# RUTAS DE TUS ARCHIVOS 
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

# Columnas categóricas a mapear (Se mapean a números antes del escalado)
CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]

# Contiene TODAS las 33 columnas: Se asume que el scaler fue ajustado a todas.
NUMERICAL_COLS_TO_SCALE = MODEL_COLUMNS

# Valores por defecto para columnas no expuestas en la UI o con valores fijos
DEFAULT_MODEL_INPUTS = {
    'PercentSalaryHike': 12, 'PerformanceRating': 3, 'TrainingTimesLastYear': 3, 
    'RelationshipSatisfaction': 3, 'WorkLifeBalance': 3,
    # Valores por defecto de categóricas
    'EducationField': 'LIFE_SCIENCES', 
    'Gender': 'MALE', 
    'MaritalStatus': 'MARRIED',
    'BusinessTravel': 'TRAVEL_RARELY',
    # Valores de satisfacción/comportamiento
    'EnvironmentSatisfaction': 3, 'JobSatisfaction': 3, 
    'CargaLaboralPercibida': 3, 'ConfianzaEmpresa': 3, 'IntencionPermanencia': 3,
    'NumeroTardanzas': 0, 'NumeroFaltas': 0
}

# Columnas clave para la simulación What-If (subconjunto para editar)
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
# FUNCIONES DE CARGA Y PREDICCIÓN (MOTOR DE 33 FEATURES)
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

def preprocess_and_predict(input_data: Dict[str, Any], model, scaler, mapping) -> tuple:
    """Preprocesa el dict de entrada (usando las 33 columnas) y realiza la predicción."""
    try:
        df_input = pd.DataFrame([input_data])
        
        # 1. Crear DataFrame Final con todas las columnas y valores de entrada/defecto
        final_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
        
        for col in MODEL_COLUMNS:
            # Transferir valores de input o usar valor por defecto
            final_df[col] = df_input[col].iloc[0] if col in df_input.columns else DEFAULT_MODEL_INPUTS.get(col, 0)
        
        # 2. Aplicar Mapeo Categórico (Label Encoding)
        for col in CATEGORICAL_COLS_TO_MAP:
            if col in mapping:
                final_df[col] = final_df[col].map(mapping[col])
                final_df[col] = final_df[col].fillna(0) 

        # 3. Aplicar Escalado A TODAS las 33 columnas
        df_to_scale = final_df[NUMERICAL_COLS_TO_SCALE].copy()
        
        scaled_values = scaler.transform(df_to_scale)
        
        # Reemplazamos TODAS las columnas escaladas
        final_df.loc[:, NUMERICAL_COLS_TO_SCALE] = scaled_values
        
        # 4. Predicción (El orden está garantizado por MODEL_COLUMNS)
        final_input = final_df[MODEL_COLUMNS].astype(float) 
        
        prediction_proba = model.predict_proba(final_input)[:, 1][0]
        predicted_class = 1 if prediction_proba >= 0.5 else 0
        
        return predicted_class, prediction_proba
        
    except Exception as e:
        st.error(f"Error durante el preprocesamiento o la predicción: {e}")
        return -1, 0.0

# --- SIMULACIÓN DE LA FUNCIÓN DE CARGA DE SUPABASE (REEMPLAZAR CON LÓGICA REAL) ---

def load_employee_data(employee_id: str, model, scaler, mapping) -> Dict[str, Any] | None:
    """
    1. Consulta Supabase (SIMULADO) para obtener datos crudos.
    2. Calcula la probabilidad actual.
    3. Devuelve los datos listos para el formulario, usando la P. Actual como P. Histórica inicial.
    """
    
    # ⚠️ REEMPLAZAR con la llamada real a Supabase (fetch_employee_data_from_supabase)
    if employee_id == "ACTIVO-001":
        employee_data_raw = {
            'employee_id': 'ACTIVO-001', 'Age': 30, 'DistanceFromHome': 5, 'Education': 3, 
            'EnvironmentSatisfaction': 2, 'JobInvolvement': 3, 'JobLevel': 2, 'JobSatisfaction': 2, 
            'MonthlyIncome': 4500, 'NumCompaniesWorked': 2, 'PercentSalaryHike': 12, 
            'PerformanceRating': 3, 'RelationshipSatisfaction': 3, 'TotalWorkingYears': 7, 
            'TrainingTimesLastYear': 3, 'WorkLifeBalance': 3, 'YearsAtCompany': 5, 
            'YearsInCurrentRole': 4, 'YearsSinceLastPromotion': 1, 'YearsWithCurrManager': 2, 
            'IntencionPermanencia': 3, 'CargaLaboralPercibida': 3, 'SatisfaccionSalarial': 2, 
            'ConfianzaEmpresa': 3, 'NumeroTardanzas': 1, 'NumeroFaltas': 0,
            'BusinessTravel': 'TRAVEL_RARELY', 'Department': 'SALES', 'EducationField': 'MARKETING', 
            'Gender': 'MALE', 'JobRole': 'SALES_EXECUTIVE', 'MaritalStatus': 'MARRIED',
            'OverTime': 'YES', 'tipo_contrato': 'PERMANENTE'
        }
    else:
        employee_data_raw = None
    
    if not employee_data_raw:
        return None
        
    # Calcular la probabilidad actual (P. Actual) usando las 33 features
    input_for_model = {k: employee_data_raw.get(k) for k in MODEL_COLUMNS if k in employee_data_raw}

    final_input_for_model = DEFAULT_MODEL_INPUTS.copy()
    final_input_for_model.update(input_for_model)

    _, prob_actual = preprocess_and_predict(final_input_for_model, model, scaler, mapping)

    # Prepara el output: La P. Actual es nuestra P. Histórica inicial para la comparación
    output_data = final_input_for_model.copy()
    output_data['Probabilidad_Historica'] = prob_actual 
    output_data['Fecha_Historial'] = 'Predicción Inicial'

    return output_data

# ====================================================================
# FUNCIONES DE RECOMENDACIÓN Y WHAT-IF
# ====================================================================

def generar_recomendacion(prob_base: float, input_data: Dict[str, Any]) -> str:
    """Genera recomendaciones basadas en reglas y la probabilidad."""
    recomendaciones = []
    
    # 1. Alerta por nivel de riesgo
    if prob_base >= 0.7:
        recomendaciones.append("**Revisión Urgente:** El riesgo es extremadamente alto.")
    elif prob_base >= 0.5:
        recomendaciones.append("Riesgo moderado/alto. Intervención recomendada.")
        
    # 2. Alerta por factores clave
    if input_data.get('MonthlyIncome', 5000) < 3000:
        recomendaciones.append("Evaluar compensación (Ingreso bajo).")
    if input_data.get('SatisfaccionSalarial', 3) <= 2:
        recomendaciones.append("Alta insatisfacción salarial.")
    if input_data.get('JobLevel', 2) == 1:
        recomendaciones.append("Fomentar planes de carrera (Nivel bajo).")
    if input_data.get('OverTime', 'NO') == 'YES':
        recomendaciones.append("Revisar carga y horas extra.")
    if input_data.get('YearsAtCompany', 3) >= 7 and input_data.get('YearsSinceLastPromotion', 1) >= 3:
         recomendaciones.append("Revisar promoción o reconocimiento (Antigüedad sin ascenso).")

    if not recomendaciones:
        return "Sin alertas específicas. El riesgo general es bajo."
        
    return " | ".join(recomendaciones)

def simular_what_if_individual(base_data: Dict[str, Any], variable_to_change: str, new_value: Any, model, scaler, mapping) -> float:
    """Ejecuta la predicción con un solo cambio para el análisis What-If."""
    # base_data contiene las 33 variables. El cambio afecta solo una, pero el motor usa todas.
    df_input = base_data.copy()
    df_input[variable_to_change] = new_value
    
    _, prob_what_if = preprocess_and_predict(df_input, model, scaler, mapping) 
    
    return prob_what_if

# ====================================================================
# FUNCIÓN DE RENDERIZADO (INTERFAZ COMPLETA CON FLUJO UNIFICADO)
# ====================================================================

def render_manual_prediction_tab():
    """Renderiza la interfaz completa de simulación, What-If e Historial."""
    
    model, scaler, mapping = load_model_artefacts() 
    if model is None or scaler is None or mapping is None:
        return

    # --- SECCIÓN: CARGA DE EMPLEADO ACTIVO ---
    st.markdown("<h2>👤 Cargar Empleado Activo para Análisis</h2>", unsafe_allow_html=True)
    
    # Reemplaza por tus IDs reales
    employee_options = ["(Ingreso Manual)", "ACTIVO-001", "ACTIVO-002"] 
    selected_id = st.selectbox(
        "Seleccionar Empleado para Precargar:", 
        options=employee_options, 
        key='employee_selector'
    )
    
    # Inicializar con valores por defecto
    initial_input = DEFAULT_MODEL_INPUTS.copy()
    initial_history = {'Probabilidad_Historica': 0.0, 'Fecha_Historial': 'N/A'}

    if selected_id != "(Ingreso Manual)":
        loaded_data = load_employee_data(selected_id, model, scaler, mapping) 
        if loaded_data:
            initial_input = {k: v for k, v in loaded_data.items() if k in MODEL_COLUMNS}
            initial_history['Probabilidad_Historica'] = loaded_data.get('Probabilidad_Historica', 0.0)
            initial_history['Fecha_Historial'] = loaded_data.get('Fecha_Historial', 'N/A')
        
    st.session_state['prob_al_cargar'] = initial_history['Probabilidad_Historica']
    st.session_state['history'] = initial_history 
    
    user_input = initial_input.copy() 
    
    # Obtener las opciones del mapping
    job_role_options = list(mapping['JobRole'].keys())
    dept_options = list(mapping['Department'].keys())
    overtime_options = list(mapping['OverTime'].keys())
    contrato_options = list(mapping['tipo_contrato'].keys())
    
    st.markdown("<h3>Modificar Datos (Formulario Rellenado)</h3>", unsafe_allow_html=True)
    
    # --- RENDERIZADO DEL FORMULARIO DE EDICIÓN (33 VARIABLES EDITABLES) ---
    col_input_1, col_input_2, col_input_3 = st.columns(3)
    
    # --- Columna 1: Demografía y Puesto ---
    with col_input_1:
        st.subheader("Puesto y Demografía")
        user_input['Age'] = st.slider("Edad", 18, 60, value=initial_input['Age'], key='age_base')
        user_input['JobLevel'] = st.slider("Nivel de Puesto (1-5)", 1, 5, value=initial_input['JobLevel'], key='joblevel_base')
        user_input['JobRole'] = st.selectbox("Puesto", job_role_options, index=job_role_options.index(initial_input['JobRole']), key='jobrole_base')
        user_input['Department'] = st.selectbox("Departamento", dept_options, index=dept_options.index(initial_input['Department']), key='dept_base')
        user_input['Education'] = st.slider("Nivel Educativo (1-5)", 1, 5, value=initial_input['Education'], key='edu_base')
        user_input['Gender'] = st.selectbox("Género", list(mapping['Gender'].keys()), index=list(mapping['Gender'].keys()).index(initial_input['Gender']), key='gender_base')

    # --- Columna 2: Compensación y Antigüedad ---
    with col_input_2:
        st.subheader("Compensación y Antigüedad")
        user_input['MonthlyIncome'] = st.number_input("Ingreso Mensual (S/.)", 1000, 25000, value=initial_input['MonthlyIncome'], key='income_base')
        user_input['TotalWorkingYears'] = st.number_input("Años Totales Trabajados", 0, 40, value=initial_input['TotalWorkingYears'], key='totalyears_base')
        user_input['YearsAtCompany'] = st.number_input("Años en la Compañía", 0, 40, value=initial_input['YearsAtCompany'], key='yearsatcomp_base')
        user_input['YearsInCurrentRole'] = st.number_input("Años en el Rol Actual", 0, 18, value=initial_input['YearsInCurrentRole'], key='yearscurrent_base')
        user_input['tipo_contrato'] = st.selectbox("Tipo de Contrato", contrato_options, index=contrato_options.index(initial_input['tipo_contrato']), key='contrato_base')
        user_input['MaritalStatus'] = st.selectbox("Estado Civil", list(mapping['MaritalStatus'].keys()), index=list(mapping['MaritalStatus'].keys()).index(initial_input['MaritalStatus']), key='marital_base')
        
    # --- Columna 3: Factores de Satisfacción y Riesgo ---
    with col_input_3:
        st.subheader("Factores de Satisfacción")
        user_input['DistanceFromHome'] = st.number_input("Distancia del Hogar (km)", 1, 30, value=initial_input['DistanceFromHome'], key='distance_base')
        user_input['OverTime'] = st.selectbox("¿Realiza Horas Extra?", overtime_options, index=overtime_options.index(initial_input['OverTime']), key='overtime_base')
        
        # Variables de Satisfacción (1-4) y Comportamiento (0+)
        user_input['EnvironmentSatisfaction'] = st.slider("Satisfacción Entorno (1-4)", 1, 4, value=initial_input['EnvironmentSatisfaction'], key='env_sat_base')
        user_input['JobSatisfaction'] = st.slider("Satisfacción Laboral (1-4)", 1, 4, value=initial_input['JobSatisfaction'], key='job_sat_base')
        user_input['SatisfaccionSalarial'] = st.slider("Satisfacción Salarial (1-4)", 1, 4, value=initial_input['SatisfaccionSalarial'], key='sal_sat_base')
        user_input['CargaLaboralPercibida'] = st.slider("Carga Laboral Percibida (1-5)", 1, 5, value=initial_input['CargaLaboralPercibida'], key='carga_base')
        user_input['ConfianzaEmpresa'] = st.slider("Confianza en la Empresa (1-4)", 1, 4, value=initial_input['ConfianzaEmpresa'], key='confianza_base')
        user_input['IntencionPermanencia'] = st.slider("Intención de Permanencia (1-5)", 1, 5, value=initial_input['IntencionPermanencia'], key='intencion_base')
        user_input['NumeroTardanzas'] = st.number_input("Número de Tardanzas (Último año)", 0, 20, value=initial_input['NumeroTardanzas'], key='tardanzas_base')
        user_input['NumeroFaltas'] = st.number_input("Número de Faltas (Último año)", 0, 20, value=initial_input['NumeroFaltas'], key='faltas_base')
        
    # --- Almacenamiento del Input para What-If ---
    st.session_state['base_input'] = user_input.copy()
    
    # --- 2. PREDICCIÓN BASE Y RESULTADOS (P. ACTUAL) ---
    st.markdown("---")
    if st.button("🔮 Ejecutar Predicción Actual", type="primary", use_container_width=True):
        
        _, prob_actual = preprocess_and_predict(user_input, model, scaler, mapping) 
        
        if prob_actual != -1.0:
            st.session_state['prob_base'] = prob_actual 
            
            recomendacion = generar_recomendacion(prob_actual, user_input)
            
            prob_al_cargar = st.session_state['prob_al_cargar']
            delta = prob_actual - prob_al_cargar
            
            # Mostramos el delta solo si el usuario cargó un empleado y modificó los datos
            if selected_id != "(Ingreso Manual)" and abs(delta) > 0.001: 
                delta_str = f"({delta * 100:+.1f} puntos porcentuales)"
                delta_line = f"""
                    <p><b>Cambio vs Datos Cargados:</b> 
                    <span style='color:{"red" if delta>0 else "green"}'>
                        {delta_str}
                    </span></p>"""
            else:
                delta_line = ""

            st.markdown(f"""
                <div style='background-color:#E3F2FD; padding:20px; border-radius:10px; text-align:center;'>
                    <h4>Resultado de Predicción ACTUAL</h4>
                    <p style='font-size:24px;'>Probabilidad de renuncia: 
                    <b style='color:{"red" if prob_actual>0.5 else "green"}'>{prob_actual:.1%}</b></p>
                    {delta_line}
                    <p><b>Recomendación:</b> {recomendacion}</p>
                </div>
            """, unsafe_allow_html=True)
    
    
    # ====================================================================
    # B. ANÁLISIS WHAT-IF (SIMULACIÓN DE ESCENARIOS)
    # ====================================================================
    
    st.markdown("<hr/>")
    st.markdown("<h3 style='color:#1f77b4;'>💡 Análisis What-If (Simulación de Escenarios)</h3>", unsafe_allow_html=True)

    if 'base_input' in st.session_state:
        prob_base_for_whatif = st.session_state.get('prob_base', None)
        if prob_base_for_whatif is None or prob_base_for_whatif == -1.0:
            st.warning("Debe ejecutar la Predicción Actual primero.")
            return

        col_what_if_1, col_what_if_2 = st.columns(2)
        
        with col_what_if_1:
            # Solo variables clave editables
            variable_key = st.selectbox(
                "Selecciona la variable a modificar:",
                options=list(WHAT_IF_VARIABLES.keys()),
                format_func=lambda x: WHAT_IF_VARIABLES[x],
                key='whatif_var_select'
            )

        with col_what_if_2:
            variable_name = WHAT_IF_VARIABLES[variable_key]
            current_value = st.session_state['base_input'].get(variable_key)
            
            # Lógica de inputs para el What-If
            if variable_key == 'MonthlyIncome':
                new_value = st.number_input(f"Nuevo valor de {variable_name} (S/.)", 1000, 30000, int(current_value * 1.1), key='whatif_new_val')
            elif variable_key in ['TotalWorkingYears', 'YearsAtCompany']:
                new_value = st.number_input(f"Nuevo valor de {variable_name}", 0, 50, current_value + 1, key='whatif_new_val_num')
            elif variable_key == 'JobLevel':
                new_value = st.slider(f"Nuevo valor de {variable_name}", 1, 5, current_value + 1 if current_value < 5 else 5, key='whatif_new_val_level')
            elif variable_key == 'OverTime':
                index = overtime_options.index(current_value) 
                new_value = st.selectbox(f"Nuevo valor de {variable_name}", overtime_options, index=index, key='whatif_new_val_cat')
            elif variable_key in ['SatisfaccionSalarial', 'ConfianzaEmpresa']:
                 new_value = st.slider(f"Nuevo valor de {variable_name}", 1, 4, current_value, key='whatif_new_val_sat')
            else:
                 new_value = st.text_input(f"Nuevo valor de {variable_name}", str(current_value), key='whatif_new_val_text')
        
        if st.button("🚀 Ejecutar What-If", key='run_what_if', use_container_width=True):
            
            prob_what_if = simular_what_if_individual(
                base_data=st.session_state['base_input'], 
                variable_to_change=variable_key,
                new_value=new_value,
                model=model,
                scaler=scaler,
                mapping=mapping 
            )
            
            if prob_what_if != -1.0:
                prob_base = st.session_state['prob_base'] 
                cambio_pct = (prob_what_if - prob_base) / prob_base * 100 if prob_base > 0 else 0
                
                st.markdown("#### 🎯 Resultados de la Simulación")
                
                col_res_1, col_res_2 = st.columns(2)
                
                with col_res_1:
                    st.metric("Prob. Base (Actual)", f"{prob_base:.1%}")
                    st.metric(
                        f"Prob. Simulada", 
                        f"{prob_what_if:.1%}", 
                        delta=f"{cambio_pct:.1f}%",
                        delta_color="inverse"
                    )
                
                with col_res_2:
                    st.info(f"El cambio de **{WHAT_IF_VARIABLES[variable_key]}** a **{new_value}** resultó en un cambio del riesgo de renuncia de **{prob_base:.1%}** a **{prob_what_if:.1%}**.")