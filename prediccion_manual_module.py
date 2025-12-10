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

EMPLOYEE_TABLE = "consolidado" # La tabla que contiene los datos
KEY_COLUMN = "EmployeeNumber" # La columna de la BD para identificar al empleado

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

def safe_index(options: list, value: Any, default_index: int = 0) -> int:
    """Busca el índice de un valor en la lista de opciones de forma segura."""
    try:
        return options.index(value)
    except ValueError:
        return default_index

@st.cache_resource
def load_model_artefacts():
    """Carga el modelo, el escalador y el mapeo categórico."""
    model, scaler, mapping = None, None, None
    try:
        # Aquí se debería manejar la carga de archivos, omitido por brevedad
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

@st.cache_data(ttl=3600)
def fetch_employee_list() -> Dict[str, str]:
    """Obtiene la lista de EmployeeNumber y Nombre para el selectbox desde Supabase."""
    supabase: Client = init_supabase_client()
    if not supabase:
        return {"(Ingreso Manual)": "(Ingreso Manual)"}
        
    try:
        # Asume que 'nombre_completo' (o similar) existe en la tabla consolidado
        response = supabase.table(consolidado).select(f"{KEY_COLUMN}, nombre_completo").execute()
        
        # Mapea los resultados: EmployeeNumber (ID) -> nombre_completo
        employee_map = {
            str(row[KEY_COLUMN]): row['nombre_completo']
            for row in response.data
        }
        return {"(Ingreso Manual)": "(Ingreso Manual)", **employee_map}
    except Exception as e:
        st.error(f"Error al obtener la lista de empleados de Supabase: {e}")
        return {"(Ingreso Manual)": "(Ingreso Manual)"}

def load_employee_data(employee_number: str, model, scaler, mapping) -> Dict[str, Any] | None:
    """
    Carga los datos reales del empleado desde Supabase (tabla 'consolidado') 
    usando EmployeeNumber y calcula la probabilidad inicial.
    """
    supabase: Client = init_supabase_client()
    if not supabase:
        return None

    try:
        # 1. Consulta a Supabase
        response = supabase.table(EMPLOYEE_TABLE).select("*").eq(KEY_COLUMN, employee_number).limit(1).execute()
        
        if not response.data:
            st.warning(f"No se encontraron datos para {KEY_COLUMN}: {employee_number} en la tabla '{EMPLOYEE_TABLE}'.")
            return None
            
        employee_data_raw = response.data[0]
        
        # 2. Preparación de los datos para el modelo
        # Esto mapea las columnas de la BD a las 33 columnas que espera el modelo (MODEL_COLUMNS)
        input_for_model = {
            k: employee_data_raw.get(k, DEFAULT_MODEL_INPUTS.get(k)) # Valor de BD, o valor por defecto
            for k in MODEL_COLUMNS
        }

        # 3. Predicción base (estado actual del empleado)
        _, prob_actual = preprocess_and_predict(input_for_model, model, scaler, mapping)

        # 4. Construir el resultado
        output_data = input_for_model.copy()
        output_data['Probabilidad_Historica'] = prob_actual 
        output_data['Fecha_Historial'] = 'Predicción Inicial'

        return output_data

    except Exception as e:
        st.error(f"❌ Error CRÍTICO al consultar/procesar datos de Supabase: {e}")
        return None

def preprocess_and_predict(input_data: Dict[str, Any], model, scaler, mapping) -> tuple:
    """Preprocesa el dict de entrada (usando las 33 columnas) y realiza la predicción."""
    try:
        df_input = pd.DataFrame([input_data])
        
        # 1. Crear DataFrame Final con todas las columnas
        final_df = pd.DataFrame(0, index=[0], columns=MODEL_COLUMNS)
        
        # Copiar los valores de entrada al DataFrame final
        for col in MODEL_COLUMNS:
            val = df_input[col].iloc[0] if col in df_input.columns else DEFAULT_MODEL_INPUTS.get(col, 0)
            final_df[col] = val
        
        # 2. Aplicar Mapeo Categórico (Label Encoding)
        for col in CATEGORICAL_COLS_TO_MAP:
            if col in mapping:
                final_df[col] = final_df[col].map(mapping[col])
                # Rellenar con 0 si la categoría no existe en el mapping
                final_df[col] = final_df[col].fillna(0) 

        # 3. Aplicar Escalado A TODAS las 33 columnas
        df_to_scale = final_df[MODEL_COLUMNS].copy()
        scaled_values = scaler.transform(df_to_scale)
        final_df.loc[:, MODEL_COLUMNS] = scaled_values
        
        # 4. Predicción
        final_input = final_df[MODEL_COLUMNS].astype(float) 
        prediction_proba = model.predict_proba(final_input)[:, 1][0]
        predicted_class = 1 if prediction_proba >= 0.5 else 0
        
        return predicted_class, prediction_proba
        
    except Exception as e:
        st.error(f"Error durante el preprocesamiento y predicción: {e}")
        return -1, 0.0

# ====================================================================
# 4. FUNCIONES DE RECOMENDACIÓN Y WHAT-IF
# ====================================================================

def generar_recomendacion(prob_base: float, input_data: Dict[str, Any]) -> str:
    """Genera recomendaciones basadas en reglas y la probabilidad."""
    recomendaciones = []
    
    # 1. Alerta por nivel de riesgo
    if prob_base >= 0.7:
        recomendaciones.append("**Revisión Urgente:** El riesgo es extremadamente alto.")
    elif prob_base >= 0.5:
        recomendaciones.append("Riesgo moderado/alto. Intervención recomendada.")
        
    # 2. Alerta por factores clave (usando los datos de entrada)
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

    if not recomendaciones and prob_base < 0.5:
        return "Nivel de riesgo **Satisfactorio**. Monitoreo constante."
        
    return " | ".join(recomendaciones)

def simular_what_if_individual(base_data: Dict[str, Any], variable_to_change: str, new_value: Any, model, scaler, mapping) -> float:
    """Ejecuta la predicción con un solo cambio para el análisis What-If."""
    df_input = base_data.copy()
    df_input[variable_to_change] = new_value
    
    _, prob_what_if = preprocess_and_predict(df_input, model, scaler, mapping) 
    
    return prob_what_if

# ====================================================================
# 5. FUNCIÓN DE RENDERIZADO (INTERFAZ COMPLETA)
# ====================================================================

def render_manual_prediction_tab():
    """Renderiza la interfaz completa de simulación, What-If e Historial."""
    
    st.set_page_config(layout="wide", page_title="Predicción de Renuncia (Churn)")
    st.title("Sistema de Predicción de Riesgo de Renuncia 📉")

    model, scaler, mapping = load_model_artefacts() 
    if model is None or scaler is None or mapping is None:
        return

    # --- SECCIÓN: CARGA DE EMPLEADO ACTIVO ---
    st.markdown("## 👤 Cargar Empleado Activo para Análisis")
    
    # Obtener la lista real de empleados de Supabase
    employee_id_to_name = fetch_employee_list() 
    
    display_options = list(employee_id_to_name.values())
    
    selected_name = st.selectbox(
        "Seleccionar Empleado para Precargar:", 
        options=display_options, 
        key='employee_selector'
    )
    
    # Obtener el ID (EmployeeNumber) seleccionado a partir del Nombre
    selected_id = [k for k, v in employee_id_to_name.items() if v == selected_name][0]

    
    # Inicializar con valores por defecto
    initial_input = DEFAULT_MODEL_INPUTS.copy() 
    initial_history = {'Probabilidad_Historica': 0.0, 'Fecha_Historial': 'N/A'}

    if selected_id != "(Ingreso Manual)":
        loaded_data = load_employee_data(selected_id, model, scaler, mapping) 
        if loaded_data:
            initial_input.update({k: v for k, v in loaded_data.items() if k in MODEL_COLUMNS})
            
            initial_history['Probabilidad_Historica'] = loaded_data.get('Probabilidad_Historica', 0.0)
            initial_history['Fecha_Historial'] = loaded_data.get('Fecha_Historial', 'Cargado de BD')
        else:
            st.warning(f"No se pudieron cargar los datos para el empleado ID: {selected_id}. Usando valores por defecto.")
            
    # Almacenar el historial y la probabilidad inicial de carga
    st.session_state['prob_al_cargar'] = initial_history['Probabilidad_Historica']
    st.session_state['history'] = initial_history 
    
    # El usuario puede modificar estos valores en el formulario
    user_input = initial_input.copy() 
    
    # Obtener las opciones del mapping para los selectboxes
    job_role_options = list(mapping.get('JobRole', {'N/A': 0}).keys())
    dept_options = list(mapping.get('Department', {'N/A': 0}).keys())
    overtime_options = list(mapping.get('OverTime', {'N/A': 0}).keys())
    contrato_options = list(mapping.get('tipo_contrato', {'N/A': 0}).keys())
    gender_options = list(mapping.get('Gender', {'N/A': 0}).keys())
    marital_options = list(mapping.get('MaritalStatus', {'N/A': 0}).keys())
    
    st.markdown("---")
    st.markdown("### 📝 Modificar Datos (Formulario Rellenado)")
    
    # --- RENDERIZADO DEL FORMULARIO DE EDICIÓN ---
    col_input_1, col_input_2, col_input_3 = st.columns(3)
    
    # --- Columna 1: Demografía y Puesto ---
    with col_input_1:
        st.subheader("Puesto y Demografía")
        user_input['Age'] = st.slider("Edad", 18, 60, value=initial_input['Age'], key='age_base')
        user_input['JobLevel'] = st.slider("Nivel de Puesto (1-5)", 1, 5, value=initial_input['JobLevel'], key='joblevel_base')
        
        user_input['JobRole'] = st.selectbox("Puesto", job_role_options, 
            index=safe_index(job_role_options, initial_input['JobRole']), key='jobrole_base')
            
        user_input['Department'] = st.selectbox("Departamento", dept_options, 
            index=safe_index(dept_options, initial_input['Department']), key='dept_base')
            
        user_input['Education'] = st.slider("Nivel Educativo (1-5)", 1, 5, value=initial_input['Education'], key='edu_base')
        
        user_input['Gender'] = st.selectbox("Género", gender_options, 
            index=safe_index(gender_options, initial_input['Gender']), key='gender_base')

    # --- Columna 2: Compensación y Antigüedad ---
    with col_input_2:
        st.subheader("Compensación y Antigüedad")
        user_input['MonthlyIncome'] = st.number_input("Ingreso Mensual (S/.)", 1000, 25000, value=initial_input['MonthlyIncome'], key='income_base')
        user_input['TotalWorkingYears'] = st.number_input("Años Totales Trabajados", 0, 40, value=initial_input['TotalWorkingYears'], key='totalyears_base')
        user_input['YearsAtCompany'] = st.number_input("Años en la Compañía", 0, 40, value=initial_input['YearsAtCompany'], key='yearsatcomp_base')
        user_input['YearsInCurrentRole'] = st.number_input("Años en el Rol Actual", 0, 18, value=initial_input['YearsInCurrentRole'], key='yearscurrent_base')
        
        user_input['tipo_contrato'] = st.selectbox("Tipo de Contrato", contrato_options, 
            index=safe_index(contrato_options, initial_input['tipo_contrato']), key='contrato_base')
            
        user_input['MaritalStatus'] = st.selectbox("Estado Civil", marital_options, 
            index=safe_index(marital_options, initial_input['MaritalStatus']), key='marital_base')
        
        user_input['PercentSalaryHike'] = st.slider("Aumento Salarial (%)", 11, 25, value=initial_input['PercentSalaryHike'], key='hike_base')
        user_input['TrainingTimesLastYear'] = st.slider("Capacitaciones (Año)", 0, 6, value=initial_input['TrainingTimesLastYear'], key='training_base')
        
    # --- Columna 3: Factores de Satisfacción y Riesgo ---
    with col_input_3:
        st.subheader("Factores de Satisfacción")
        user_input['DistanceFromHome'] = st.number_input("Distancia del Hogar (km)", 1, 30, value=initial_input['DistanceFromHome'], key='distance_base')
        
        user_input['OverTime'] = st.selectbox("¿Realiza Horas Extra?", overtime_options, 
            index=safe_index(overtime_options, initial_input['OverTime']), key='overtime_base')
        
        # Factores de Satisfacción (1-4)
        user_input['EnvironmentSatisfaction'] = st.slider("Satisfacción Entorno (1-4)", 1, 4, value=initial_input['EnvironmentSatisfaction'], key='env_sat_base')
        user_input['JobSatisfaction'] = st.slider("Satisfacción Laboral (1-4)", 1, 4, value=initial_input['JobSatisfaction'], key='job_sat_base')
        user_input['SatisfaccionSalarial'] = st.slider("Satisfacción Salarial (1-4)", 1, 4, value=initial_input['SatisfaccionSalarial'], key='sal_sat_base')
        user_input['ConfianzaEmpresa'] = st.slider("Confianza en la Empresa (1-4)", 1, 4, value=initial_input['ConfianzaEmpresa'], key='confianza_base')

        # Factores de Comportamiento (1-5 o Numéricos)
        user_input['CargaLaboralPercibida'] = st.slider("Carga Laboral Percibida (1-5)", 1, 5, value=initial_input['CargaLaboralPercibida'], key='carga_base')
        user_input['IntencionPermanencia'] = st.slider("Intención de Permanencia (1-5)", 1, 5, value=initial_input['IntencionPermanencia'], key='intencion_base')
        user_input['NumeroTardanzas'] = st.number_input("Número de Tardanzas (Último año)", 0, 20, value=initial_input['NumeroTardanzas'], key='tardanzas_base')
        user_input['NumeroFaltas'] = st.number_input("Número de Faltas (Último año)", 0, 20, value=initial_input['NumeroFaltas'], key='faltas_base')
        
    # Almacenamiento del Input para What-If (será la base)
    st.session_state['base_input'] = user_input.copy()
    
    # --------------------------------------------------------------------
    # --- PREDICCIÓN BASE Y RESULTADOS ---
    # --------------------------------------------------------------------
    st.markdown("---")
    
    # Lógica de la predicción actual, ahora también se usa para el what-if base
    prob_base_actual = st.session_state.get('prob_base', 0.0)

    if st.button("🔮 Ejecutar Predicción Actual", type="primary", use_container_width=True):
        
        _, prob_actual = preprocess_and_predict(user_input, model, scaler, mapping) 
        
        if prob_actual != -1.0:
            st.session_state['prob_base'] = prob_actual 
            prob_base_actual = prob_actual # Actualiza la variable local para el renderizado
            
            recomendacion_str = generar_recomendacion(prob_actual, user_input)
            
            prob_al_cargar = st.session_state['prob_al_cargar']
            delta = prob_actual - prob_al_cargar
            
            st.markdown("### Resultado de Predicción ACTUAL")
            
            col_metric, col_info = st.columns([1, 2])
            
            # 1. Métrica Principal (Probabilidad)
            with col_metric:
                
                delta_str = None
                if selected_id != "(Ingreso Manual)" and abs(delta) > 0.001:
                    delta_str = f"{delta * 100:+.1f} p.p. vs Carga Inicial"

                st.metric(
                    label="Probabilidad de renuncia",
                    value=f"{prob_actual:.1%}",
                    delta=delta_str,
                    delta_color="inverse" # Muestra positivo (aumento de riesgo) en rojo
                )

            # 2. Recomendación
            with col_info:
                if prob_actual >= 0.5:
                    st.warning(f"🚨 **Recomendación/Alerta:** {recomendacion_str}")
                else:
                    st.info(f"✅ **Estado:** {recomendacion_str}")

                with st.expander("Detalles de la Simulación"):
                    st.write("Variables de entrada:")
                    st.json(user_input) 
    
    
    # ====================================================================
    # B. ANÁLISIS WHAT-IF (SIMULACIÓN DE ESCENARIOS) - AUTÓNOMO
    # ====================================================================
    
    st.markdown("---")
    st.markdown("## 💡 Análisis What-If (Simulación de Escenarios)")
    
    # Si la probabilidad base no existe, la calculamos implícitamente
    if 'prob_base' not in st.session_state or st.session_state['prob_base'] == 0.0:
         _, prob_base_actual = preprocess_and_predict(user_input, model, scaler, mapping)
         st.session_state['prob_base'] = prob_base_actual
    
    prob_base_for_whatif = st.session_state.get('prob_base', prob_base_actual)
    
    if prob_base_for_whatif <= 0.0:
        st.warning("No se pudo calcular la probabilidad base. Revise los datos de entrada o la conexión al modelo.")
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
        current_value = st.session_state['base_input'].get(variable_key)
        
        # Lógica de inputs para el What-If
        if variable_key == 'MonthlyIncome':
            # Sugerir un aumento del 10%
            suggested_value = int(current_value * 1.1) if current_value else 5500
            new_value = st.number_input(f"Nuevo valor de {variable_name} (S/.)", 1000, 30000, suggested_value, key='whatif_new_val')
        elif variable_key in ['TotalWorkingYears', 'YearsAtCompany']:
            # Sugerir un aumento de 1 año
            new_value = st.number_input(f"Nuevo valor de {variable_name}", 0, 50, current_value + 1 if current_value < 50 else current_value, key='whatif_new_val_num')
        elif variable_key == 'JobLevel':
            # Sugerir un ascenso
            new_value = st.slider(f"Nuevo valor de {variable_name}", 1, 5, current_value + 1 if current_value < 5 else 5, key='whatif_new_val_level')
        elif variable_key == 'OverTime':
            # Sugerir eliminar horas extra
            new_value = st.selectbox(f"Nuevo valor de {variable_name}", overtime_options, index=safe_index(overtime_options, 'NO'), key='whatif_new_val_cat')
        elif variable_key in ['SatisfaccionSalarial', 'ConfianzaEmpresa']:
            # Sugerir aumento de satisfacción
            new_value = st.slider(f"Nuevo valor de {variable_name}", 1, 4, current_value + 1 if current_value < 4 else 4, key='whatif_new_val_sat')
        else:
            new_value = st.text_input(f"Nuevo valor de {variable_name}", str(current_value), key='whatif_new_val_text')
    
    if st.button("🚀 Ejecutar What-If", key='run_what_if', use_container_width=True):
        
        # Validación
        if new_value == current_value:
             st.warning("El nuevo valor es idéntico al valor base. No hay cambio para simular.")
             return

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
            cambio_abs = prob_what_if - prob_base
            
            st.markdown("#### 🎯 Resultados de la Simulación")
            
            col_res_1, col_res_2 = st.columns(2)
            
            with col_res_1:
                st.metric("Prob. Base (Actual)", f"{prob_base:.1%}")
                st.metric(
                    f"Prob. Simulada", 
                    f"{prob_what_if:.1%}", 
                    delta=f"{cambio_abs * 100:+.1f} p.p. de cambio", # Cambio en puntos porcentuales
                    delta_color="inverse"
                )
            
            with col_res_2:
                st.info(f"El cambio de **{WHAT_IF_VARIABLES[variable_key]}** (valor base: **{current_value}**) a **{new_value}** resultó en un cambio del riesgo de renuncia de **{prob_base:.1%}** a **{prob_what_if:.1%}**.")
                
if __name__ == '__main__':
    render_manual_prediction_tab()