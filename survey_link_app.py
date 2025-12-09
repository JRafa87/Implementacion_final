import streamlit as st
from supabase import create_client, Client
from datetime import datetime
from typing import Optional
import pandas as pd

# ==============================================================================
# 0. CONFIGURACIÓN, CONEXIÓN Y ESTADO INICIAL
# ==============================================================================

@st.cache_resource
def get_supabase() -> Optional[Client]:
    """Inicializa y cachea el cliente de Supabase."""
    # Tu lógica para leer SUPABASE_URL y SUPABASE_KEY desde secrets.toml
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan credenciales de Supabase en secrets.toml.")
        st.stop()
    try:
        return create_client(url, key)
    except Exception:
        st.error("Error al conectar con la BD.")
        st.stop()
supabase = get_supabase()

def save_survey_to_supabase(data: dict):
    """Guarda los datos de la encuesta en la tabla 'encuestas'."""
    if supabase is None: return False
    try:
        # Inserta los datos con los nombres de columna EXACTOS
        response = supabase.table("encuestas").insert(data).execute()
        return bool(response.data)
    except Exception as e:
        # Error común: UNIQUE constraint violation (ya respondió)
        st.error(f"Error al guardar. Revise las escalas o su ID ya respondió: {e}")
        return False

# --- Funciones de Lectura de Control ---

@st.cache_data(ttl=5)
def get_survey_config():
    """Obtiene el estado de la configuración de la encuesta desde Supabase."""
    if supabase is None: return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}
    try:
        response = supabase.table("configuracion_encuesta").select("*").execute()
        return {item['clave']: item['valor'] for item in response.data}
    except Exception:
        return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}

@st.cache_data(ttl=600)
def get_employee_status_and_dept(employee_id: int):
    """Verifica si el empleado existe, está activo (FechaSalida es NULL) y retorna su departamento."""
    if supabase is None: return False, None
    try:
        # Busca si es activo (FechaSalida es NULL)
        response = supabase.table("empleados").select("Department, FechaSalida") \
            .eq("EmployeeNumber", employee_id) \
            .limit(1) \
            .execute()
        
        if not response.data: return False, None # No existe
            
        data = response.data[0]
        # is_active es True si 'FechaSalida' es None (NULL)
        is_active = data.get('FechaSalida') is None 
        dept = data.get('Department')
        
        return is_active, dept
        
    except Exception:
        return False, None

# ==============================================================================
# 2. RENDERIZADO DEL FORMULARIO PÚBLICO
# ==============================================================================

def render_public_survey():
    st.set_page_config(page_title="Encuesta Laboral", layout="centered")
    st.title("🗣️ Encuesta de Satisfacción Laboral")
    
    # Inicialización del estado de verificación
    if 'employee_verified' not in st.session_state:
        st.session_state['employee_verified'] = False
        st.session_state['employee_id_validated'] = 0
        st.session_state['employee_dept'] = None
    
    # --- 1. Controles y Habilitación ---
    config = get_survey_config()
    is_globally_enabled = config.get('encuesta_habilitada_global') == 'true'
    enabled_dept = config.get('departamento_habilitado', 'NINGUNO')

    # Contenedor para el primer paso: Identificación
    with st.container(border=True):
        st.subheader("Paso 1: Tu Número de Identificación")
        
        # Campo de entrada
        employee_id = st.number_input(
            "Ingresa tu EmployeeNumber para verificar tu acceso:", 
            min_value=1, 
            step=1, 
            key='employee_id_input_public',
            placeholder="Ej: 1001"
        )
        
        # Botón para verificar
        if st.button("Verificar Acceso 🔎"):
            
            is_active, employee_dept = get_employee_status_and_dept(employee_id)
            
            # --- VALIDACIÓN 1: Existencia y Actividad ---
            if not is_active:
                st.error("❌ Acceso Denegado. El ID no está activo o no existe.")
                st.session_state['employee_verified'] = False
                return
            
            # --- VALIDACIÓN 2: Control Central (Administrador) ---
            is_permitted = is_globally_enabled or (employee_dept == enabled_dept)
            
            if not is_permitted:
                st.session_state['employee_verified'] = False
                if enabled_dept == "NINGUNO":
                    st.error("🔒 La encuesta está **deshabilitada totalmente** por la administración.")
                else:
                    st.error(f"🔒 La encuesta está habilitada **SOLAMENTE** para el área de **{enabled_dept}**.")
                return
            
            # --- ACCESO CONCEDIDO ---
            st.session_state['employee_verified'] = True
            st.session_state['employee_id_validated'] = employee_id
            st.session_state['employee_dept'] = employee_dept
            st.toast("✅ ¡Acceso verificado! Ya puedes llenar el formulario.", icon="🥳")
            st.rerun() # Volver a correr para desbloquear el formulario

    # --- 2. Formulario de Encuesta (Se habilita solo si está verificado) ---
    is_verified = st.session_state.get('employee_verified', False)
    
    # Usa 'disabled' para bloquear los inputs de la encuesta si no está verificado
    with st.form(key='survey_data_form', clear_on_submit=False, border=is_verified):
        
        st.subheader("Paso 2: Responde el Cuestionario")
        st.caption("Puedes cambiar tus respuestas libremente antes de enviar.")
        
        if not is_verified:
            st.warning("⚠️ Debes verificar tu EmployeeNumber arriba para desbloquear la encuesta.")
        
        # --- Campos Ocultos (para envío) ---
        employee_id_validated = st.session_state.get('employee_id_validated', 0)
        
        # --- Ítems Escala 1-4 (Deshabilitados si no está verificado) ---
        st.markdown("##### Factores de Clima Laboral (1 = Muy en Desacuerdo, 4 = Muy de Acuerdo)")
        
        # EnvironmentSatisfaction
        EnvironmentSatisfaction = st.radio("1. Ambiente de Trabajo:", options=[4, 3, 2, 1], index=2, horizontal=True, disabled=not is_verified)
        
        # JobInvolvement
        JobInvolvement = st.radio("2. Nivel de Compromiso:", options=[4, 3, 2, 1], index=1, horizontal=True, disabled=not is_verified)
        
        # JobSatisfaction
        JobSatisfaction = st.radio("3. Satisfacción con Tareas:", options=[4, 3, 2, 1], index=1, horizontal=True, disabled=not is_verified)

        # RelationshipSatisfaction
        RelationshipSatisfaction = st.radio("4. Relaciones Laborales:", options=[4, 3, 2, 1], index=1, horizontal=True, disabled=not is_verified)
        
        # WorkLifeBalance
        WorkLifeBalance = st.radio("5. Equilibrio Vida Laboral:", options=[4, 3, 2, 1], index=2, horizontal=True, disabled=not is_verified)
        
        # IntencionPermanencia
        IntencionPermanencia = st.radio("6. Intención de Permanencia:", options=[4, 3, 2, 1], index=1, horizontal=True, disabled=not is_verified)

        # ConfianzaEmpresa
        ConfianzaEmpresa = st.radio("7. Confianza en la Dirección:", options=[4, 3, 2, 1], index=1, horizontal=True, disabled=not is_verified)


        # --- Ítems Escala 1-5 ---
        st.markdown("##### Percepción (1 = Muy Bajo, 5 = Muy Alto)")
        
        # CargaLaboralPercibida
        CargaLaboralPercibida = st.slider("8. Carga Laboral Percibida:", min_value=1, max_value=5, value=3, step=1, disabled=not is_verified)
        
        # SatisfaccionSalarial
        SatisfaccionSalarial = st.slider("9. Satisfacción Salarial:", min_value=1, max_value=5, value=3, step=1, disabled=not is_verified)
        
        # --- Botón de Envío ---
        submit_button = st.form_submit_button(label='Enviar Respuestas 📤', disabled=not is_verified, type="primary")

        if submit_button:
            # 3. Lógica de Envío
            survey_data = {
                "EmployeeNumber": employee_id_validated,
                "EnvironmentSatisfaction": EnvironmentSatisfaction,
                "JobInvolvement": JobInvolvement,
                "JobSatisfaction": JobSatisfaction,
                "RelationshipSatisfaction": RelationshipSatisfaction,
                "WorkLifeBalance": WorkLifeBalance,
                "IntencionPermanencia": IntencionPermanencia,
                "CargaLaboralPercibida": CargaLaboralPercibida,
                "SatisfaccionSalarial": SatisfaccionSalarial,
                "ConfianzaEmpresa": ConfianzaEmpresa,
                "Fecha": datetime.now().strftime('%Y-%m-%d')
            }
            
            if save_survey_to_supabase(survey_data):
                # Mensaje de agradecimiento y limpieza
                st.session_state['employee_verified'] = False 
                st.session_state['employee_id_validated'] = 0 
                st.balloons()
                st.success("🎉 ¡Encuesta enviada! Muchas gracias por tus respuestas.")
                st.markdown("Puedes cerrar esta ventana o ingresar un nuevo ID.")
            else:
                st.error("Hubo un error al guardar los datos.")

if __name__ == "__main__":
    render_public_survey()