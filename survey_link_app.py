import streamlit as st
from supabase import create_client, Client
from datetime import datetime
from typing import Optional

# ==============================================================================
# 0. CONFIGURACIÓN Y MAPEO
# ==============================================================================

MAPEO_DEPTOS = {
    "Sales": "Ventas", 
    "Research & Development": "Investigación y Desarrollo", 
    "Human Resources": "Recursos Humanos"
}

@st.cache_resource
def get_supabase() -> Optional[Client]:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan credenciales de Supabase.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# ==============================================================================
# 1. FUNCIONES DE LÓGICA Y CONSULTA
# ==============================================================================

@st.cache_data(ttl=5)
def get_survey_config():
    """Obtiene la configuración de control (Global y Departamento)."""
    try:
        response = supabase.table("configuracion_encuesta").select("*").execute()
        return {item['clave']: item['valor'] for item in response.data}
    except Exception:
        return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}

@st.cache_data(ttl=600)
def get_employee_details(employee_id: int):
    """
    SIEMPRE verifica si el empleado está activo.
    Retorna (is_active, department_name)
    """
    try:
        # Consultamos el empleado por su ID
        response = supabase.table("empleados").select("Department, FechaSalida") \
            .eq("EmployeeNumber", employee_id) \
            .limit(1).execute()
        
        if not response.data: 
            return False, None # No existe el ID
            
        data = response.data[0]
        # REGLA DE ORO: Solo es activo si 'FechaSalida' es NULL
        is_active = data.get('FechaSalida') is None 
        dept = data.get('Department')
        
        return is_active, dept
    except Exception:
        return False, None

def save_survey_to_supabase(data: dict):
    try:
        response = supabase.table("encuestas").insert(data).execute()
        return bool(response.data)
    except Exception as e:
        st.error(f"Error: Es posible que ya hayas respondido esta encuesta.")
        return False

# ==============================================================================
# 2. RENDERIZADO DE LA ENCUESTA
# ==============================================================================

def render_public_survey():
    st.set_page_config(page_title="Encuesta Laboral", layout="centered")
    st.title("🗣️ Encuesta de Satisfacción Laboral")
    
    if 'employee_verified' not in st.session_state:
        st.session_state['employee_verified'] = False
        st.session_state['employee_id_validated'] = 0
        st.session_state['employee_dept'] = None

    # --- LECTURA DE CONFIGURACIÓN DEL ADMIN ---
    config = get_survey_config()
    is_globally_enabled = config.get('encuesta_habilitada_global') == 'true'
    enabled_dept_db = config.get('departamento_habilitado', 'NINGUNO')

    # --- PASO 1: VERIFICACIÓN ---
    with st.container(border=True):
        st.subheader("Paso 1: Identificación")
        
        employee_id = st.number_input("Ingresa tu ID de Empleado:", min_value=1, step=1, key='id_input')
        
        if st.button("Verificar mi Acceso 🔎"):
            # PRIMERA VALIDACIÓN: ¿ESTÁ ACTIVO? (Independiente de todo lo demás)
            is_active, employee_dept_eng = get_employee_details(employee_id)
            
            if not is_active:
                st.error("❌ Acceso Denegado. Este ID no existe o el colaborador ya no se encuentra activo en la empresa.")
                st.session_state['employee_verified'] = False
                return

            # SEGUNDA VALIDACIÓN: ¿TIENE PERMISO POR ÁREA O GLOBAL?
            is_permitted = is_globally_enabled or (employee_dept_eng == enabled_dept_db)

            if not is_permitted:
                st.session_state['employee_verified'] = False
                if enabled_dept_db == "NINGUNO":
                    st.error("🔒 La encuesta está cerrada temporalmente para todos los departamentos.")
                else:
                    depto_permitido_esp = MAPEO_DEPTOS.get(enabled_dept_db, enabled_dept_db)
                    st.error(f"🔒 Acceso denegado. Actualmente la encuesta solo recibe respuestas del área de: **{depto_permitido_esp}**.")
                return

            # --- ACCESO EXITOSO ---
            st.session_state['employee_verified'] = True
            st.session_state['employee_id_validated'] = employee_id
            st.session_state['employee_dept'] = MAPEO_DEPTOS.get(employee_dept_eng, employee_dept_eng)
            st.toast("ID Verificado correctamente", icon="✅")
            st.rerun()

    # --- MENSAJE DE BIENVENIDA ---
    if st.session_state['employee_verified']:
        st.success(f"✅ **Bienvenido.** Se ha validado tu ID como miembro activo del área de **{st.session_state['employee_dept']}**.")
    
    # --- PASO 2: EL FORMULARIO ---
    is_verified = st.session_state.get('employee_verified', False)
    
    with st.form(key='survey_data_form'):
        st.subheader("Paso 2: Cuestionario")
        
        if not is_verified:
            st.warning("⚠️ Ingresa tu ID arriba y presiona 'Verificar mi Acceso' para habilitar las preguntas.")
        
        # --- PREGUNTAS (Bloqueadas si no está verificado) ---
        env_sat = st.radio("1. Ambiente de Trabajo:", [4, 3, 2, 1], horizontal=True, disabled=not is_verified)
        job_inv = st.radio("2. Compromiso:", [4, 3, 2, 1], horizontal=True, disabled=not is_verified)
        job_sat = st.radio("3. Satisfacción:", [4, 3, 2, 1], horizontal=True, disabled=not is_verified)
        rel_sat = st.radio("4. Relaciones:", [4, 3, 2, 1], horizontal=True, disabled=not is_verified)
        wlb = st.radio("5. Equilibrio Vida:", [4, 3, 2, 1], horizontal=True, disabled=not is_verified)
        int_perm = st.radio("6. Permanencia:", [4, 3, 2, 1], horizontal=True, disabled=not is_verified)
        conf_dir = st.radio("7. Confianza:", [4, 3, 2, 1], horizontal=True, disabled=not is_verified)
        
        st.markdown("---")
        carga = st.slider("8. Carga Laboral (1-5):", 1, 5, 3, disabled=not is_verified)
        salario = st.slider("9. Satisfacción Salarial (1-5):", 1, 5, 3, disabled=not is_verified)

        submit = st.form_submit_button("Enviar Respuestas 📤", disabled=not is_verified, type="primary")

        if submit:
            data = {
                "EmployeeNumber": st.session_state['employee_id_validated'],
                "EnvironmentSatisfaction": env_sat,
                "JobInvolvement": job_inv,
                "JobSatisfaction": job_sat,
                "RelationshipSatisfaction": rel_sat,
                "WorkLifeBalance": wlb,
                "IntencionPermanencia": int_perm,
                "ConfianzaEmpresa": conf_dir,
                "CargaLaboralPercibida": carga,
                "SatisfaccionSalarial": salario,
                "Fecha": datetime.now().strftime('%Y-%m-%d')
            }
            
            if save_survey_to_supabase(data):
                st.balloons()
                st.success("🎉 ¡Muchas gracias! Tu encuesta ha sido enviada con éxito.")
                st.session_state['employee_verified'] = False # Resetear para el siguiente
                st.info("Ya puedes cerrar esta pestaña.")

if __name__ == "__main__":
    render_public_survey()