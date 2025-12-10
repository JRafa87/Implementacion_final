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
# CONFIGURACIÓN DEL MODELO Y ARTEFACTOS (ORDEN ESTRICTO)
# ====================================================================

# RUTAS DE TUS ARCHIVOS (Asumimos que están en 'models/')
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

# Columnas categóricas a mapear (NO SE ESCALAN)
CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]

# Columnas numéricas/ordinales que DEBEN ser escaladas (Son el resto)
NUMERICAL_COLS_TO_SCALE = [
    'Age', 'DistanceFromHome', 'Education', 'EnvironmentSatisfaction',
    'JobInvolvement', 'JobLevel', 'JobSatisfaction', 'MonthlyIncome', 
    'NumCompaniesWorked', 'PercentSalaryHike', 'PerformanceRating', 
    'RelationshipSatisfaction', 'TotalWorkingYears', 'TrainingTimesLastYear', 
    'WorkLifeBalance', 'YearsAtCompany', 'YearsInCurrentRole', 
    'YearsSinceLastPromotion', 'YearsWithCurrManager',
    'IntencionPermanencia', 'CargaLaboralPercibida', 'SatisfaccionSalarial', 
    'ConfianzaEmpresa', 'NumeroTardanzas', 'NumeroFaltas' 
]

# Valores por defecto para columnas que no se piden en la interfaz o tienen valores fijos
DEFAULT_MODEL_INPUTS = {
    'PercentSalaryHike': 12, 'PerformanceRating': 3, 'TrainingTimesLastYear': 3, 
    'RelationshipSatisfaction': 3, 'WorkLifeBalance': 3,
    # Valores por defecto de categóricas (usando el valor del mapeo)
    'EducationField': 'LIFE_SCIENCES', 
    'Gender': 'MALE', 
    'MaritalStatus': 'MARRIED',
    'BusinessTravel': 'TRAVEL_RARELY',
    # Valores de satisfacción/comportamiento
    'EnvironmentSatisfaction': 3, 'JobSatisfaction': 3, 
    'CargaLaboralPercibida': 3, 'ConfianzaEmpresa': 3, 'IntencionPermanencia': 3,
    'NumeroTardanzas': 0, 'NumeroFaltas': 0
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
# FUNCIONES DE CARGA Y PREDICCIÓN (Lógica CLAVE para Feature Match)
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
    """Preprocesa el dict de entrada, asegura el orden y realiza la predicción."""
    try:
        df_input = pd.DataFrame([input_data])
        
        # 1. Crear DataFrame Final con todas las columnas y valores de entrada/defecto
        final_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
        
        for col in MODEL_COLUMNS:
            # Transferir valores de input o usar valor por defecto
            # Esto debe usarse solo para variables no categóricas que tienen valores por defecto si no están en el input
            final_df[col] = df_input[col].iloc[0] if col in df_input.columns else DEFAULT_MODEL_INPUTS.get(col, 0)
        
        # 2. Aplicar Mapeo Categórico (Label Encoding)
        for col in CATEGORICAL_COLS_TO_MAP:
            if col in mapping:
                # Mapear el valor de texto al número entero
                final_df[col] = final_df[col].map(mapping[col])
                # Es crucial que aquí no queden NaNs (valores que no se mapearon)
                # Si una categoría es desconocida, rellenar con un valor seguro (ej: la moda o -1)
                final_df[col] = final_df[col].fillna(0) 

        # 3. Aplicar Escalado SÓLO a las columnas numéricas/ordinales
        df_to_scale = final_df[NUMERICAL_COLS_TO_SCALE].copy()
        
        scaled_values = scaler.transform(df_to_scale)
        
        # Reemplazamos SÓLO las columnas escaladas en el DataFrame final
        final_df.loc[:, NUMERICAL_COLS_TO_SCALE] = scaled_values
        
        # 4. Predicción (El orden está garantizado por MODEL_COLUMNS)
        final_input = final_df[MODEL_COLUMNS].astype(float) # Aquí se usa el orden exacto
        
        prediction_proba = model.predict_proba(final_input)[:, 1][0]
        predicted_class = 1 if prediction_proba >= 0.5 else 0
        
        return predicted_class, prediction_proba
        
    except Exception as e:
        st.error(f"Error durante el preprocesamiento o la predicción: {e}")
        return -1, 0.0

# ====================================================================
# FUNCIONES DE RECOMENDACIÓN Y WHAT-IF (Inclusión COMPLETA)
# ====================================================================

def generar_recomendacion(prob_base: float, input_data: Dict[str, Any]) -> str:
    """Genera recomendaciones basadas en reglas y la probabilidad."""
    recomendaciones = []
    
    # 1. Alerta por nivel de riesgo
    if prob_base >= 0.7:
        recomendaciones.append("**Revisión Urgente:** El riesgo es extremadamente alto.")
    elif prob_base >= 0.5:
        recomendaciones.append("Riesgo moderado/alto. Intervención recomendada.")
        
    # 2. Alerta por factores clave (Usando las nuevas columnas)
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
    df_input = base_data.copy()
    df_input[variable_to_change] = new_value
    
    _, prob_what_if = preprocess_and_predict(df_input, model, scaler, mapping) 
    
    return prob_what_if

# ====================================================================
# FUNCIÓN DE RENDERIZADO (INTERFAZ COMPLETA)
# ====================================================================

def render_manual_prediction_tab():
    """Renderiza la interfaz completa de simulación y What-If en Streamlit."""
    
    model, scaler, mapping = load_model_artefacts() 
    if model is None or scaler is None or mapping is None:
        return

    st.markdown("<h3 style='color:#1f77b4;'>Ingrese los Datos del Empleado</h3>", unsafe_allow_html=True)
    
    user_input = DEFAULT_MODEL_INPUTS.copy()
    
    # Obtener las opciones del mapping
    job_role_options = list(mapping['JobRole'].keys())
    dept_options = list(mapping['Department'].keys())
    overtime_options = list(mapping['OverTime'].keys())
    contrato_options = list(mapping['tipo_contrato'].keys())
    
    col_input_1, col_input_2, col_input_3 = st.columns(3)
    
    # --- Columna 1: Demografía y Puesto ---
    with col_input_1:
        st.subheader("Puesto y Demografía")
        user_input['Age'] = st.slider("Edad", 18, 60, 30, key='age_base')
        user_input['JobLevel'] = st.slider("Nivel de Puesto (1-5)", 1, 5, 2, key='joblevel_base')
        user_input['JobRole'] = st.selectbox("Puesto", job_role_options, key='jobrole_base')
        user_input['Department'] = st.selectbox("Departamento", dept_options, key='dept_base')
        user_input['Education'] = st.slider("Nivel Educativo (1-5)", 1, 5, 3, key='edu_base')
        user_input['Gender'] = st.selectbox("Género", list(mapping['Gender'].keys()), key='gender_base')

    # --- Columna 2: Compensación y Antigüedad ---
    with col_input_2:
        st.subheader("Compensación y Antigüedad")
        user_input['MonthlyIncome'] = st.number_input("Ingreso Mensual (S/.)", 1000, 25000, 5000, key='income_base')
        user_input['TotalWorkingYears'] = st.number_input("Años Totales Trabajados", 0, 40, 5, key='totalyears_base')
        user_input['YearsAtCompany'] = st.number_input("Años en la Compañía", 0, 40, 3, key='yearsatcomp_base')
        user_input['YearsInCurrentRole'] = st.number_input("Años en el Rol Actual", 0, 18, 2, key='yearscurrent_base')
        user_input['tipo_contrato'] = st.selectbox("Tipo de Contrato", contrato_options, key='contrato_base')
        user_input['MaritalStatus'] = st.selectbox("Estado Civil", list(mapping['MaritalStatus'].keys()), key='marital_base')
        
    # --- Columna 3: Factores de Satisfacción y Riesgo ---
    with col_input_3:
        st.subheader("Factores de Satisfacción")
        user_input['DistanceFromHome'] = st.number_input("Distancia del Hogar (km)", 1, 30, 10, key='distance_base')
        user_input['OverTime'] = st.selectbox("¿Realiza Horas Extra?", overtime_options, key='overtime_base')
        
        # Variables de Satisfacción (1-4) y Comportamiento (0+)
        user_input['EnvironmentSatisfaction'] = st.slider("Satisfacción Entorno (1-4)", 1, 4, 3, key='env_sat_base')
        user_input['JobSatisfaction'] = st.slider("Satisfacción Laboral (1-4)", 1, 4, 3, key='job_sat_base')
        user_input['SatisfaccionSalarial'] = st.slider("Satisfacción Salarial (1-4)", 1, 4, 3, key='sal_sat_base')
        user_input['CargaLaboralPercibida'] = st.slider("Carga Laboral Percibida (1-5)", 1, 5, 3, key='carga_base')
        user_input['ConfianzaEmpresa'] = st.slider("Confianza en la Empresa (1-4)", 1, 4, 3, key='confianza_base')
        user_input['IntencionPermanencia'] = st.slider("Intención de Permanencia (1-5)", 1, 5, 3, key='intencion_base')
        user_input['NumeroTardanzas'] = st.number_input("Número de Tardanzas (Último año)", 0, 20, 0, key='tardanzas_base')
        user_input['NumeroFaltas'] = st.number_input("Número de Faltas (Último año)", 0, 20, 0, key='faltas_base')
        
    # --- Almacenamiento del Input para What-If ---
    st.session_state['base_input'] = user_input.copy()
    
    # --- 2. PREDICCIÓN BASE Y RESULTADOS ---
    st.markdown("---")
    if st.button("🔮 Ejecutar Predicción Base", type="primary", use_container_width=True):
        
        _, prob_base = preprocess_and_predict(user_input, model, scaler, mapping) 
        
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
    # B. ANÁLISIS WHAT-IF (INDEPENDIENTE)
    # ====================================================================
    
    st.markdown("<hr/>")
    st.markdown("<h3 style='color:#1f77b4;'>💡 Análisis What-If (Simulación de Escenarios)</h3>", unsafe_allow_html=True)

    if 'base_input' in st.session_state:
        base_input = st.session_state['base_input']
        
        # 1. Obtener la probabilidad base (calculándola si es necesario)
        prob_base_for_whatif = st.session_state.get('prob_base', None)
        if prob_base_for_whatif is None or prob_base_for_whatif == -1.0:
            _, prob_base_for_whatif = preprocess_and_predict(base_input, model, scaler, mapping)
            st.session_state['prob_base'] = prob_base_for_whatif
        
        if prob_base_for_whatif == -1.0:
            st.warning("No se puede realizar el What-If. Corrija los errores de predicción base.")
            return

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
            elif variable_key in ['SatisfaccionSalarial', 'ConfianzaEmpresa']:
                 new_value = st.slider(f"Nuevo valor de {variable_name}", 1, 4, current_value, key='whatif_new_val_sat')
            else:
                 new_value = st.text_input(f"Nuevo valor de {variable_name}", str(current_value), key='whatif_new_val_text')
        
        if st.button("🚀 Ejecutar What-If", key='run_what_if', use_container_width=True):
            
            prob_what_if = simular_what_if_individual(
                base_data=base_input,
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
        st.info("💡 Complete los datos del formulario arriba para que el What-If funcione automáticamente.")