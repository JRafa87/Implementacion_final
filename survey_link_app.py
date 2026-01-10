import streamlit as st
from supabase import create_client, Client
from datetime import datetime
from typing import Optional

# ==============================================================================
# 1. CONFIGURACIÓN VISUAL Y ESTILOS
# ==============================================================================
st.set_page_config(page_title="Encuesta de Clima Laboral", layout="centered", page_icon="🗣️")

# CSS para mejorar la apariencia de las tarjetas y mensajes
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .stForm { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .welcome-box { padding: 15px; border-radius: 10px; border-left: 5px solid #28a745; background-color: #e9f7ef; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONFIGURACIÓN Y CONEXIÓN
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
        st.error("Error: Credenciales de base de datos no configuradas.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# ==============================================================================
# 3. LÓGICA DE NEGOCIO (BACKEND)
# ==============================================================================

@st.cache_data(ttl=2)
def get_survey_config():
    """Obtiene la configuración de control."""
    try:
        response = supabase.table("configuracion_encuesta").select("*").execute()
        return {item['clave']: item['valor'] for item in response.data}
    except Exception:
        return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}

def get_employee_status(employee_id: int):
    """
    VALDIACIÓN ESTRICTA: 
    Trae los datos y verifica en Python si el empleado es realmente activo.
    """
    try:
        res = supabase.table("empleados").select("Department, FechaSalida").eq("EmployeeNumber", employee_id).execute()
        if not res.data:
            return False, None, "ID no encontrado"
        
        emp = res.data[0]
        fecha_salida = emp.get('FechaSalida')
        
        # Un empleado es activo SOLO SI FechaSalida es NULL, None o vacío
        es_activo = (fecha_salida is None or str(fecha_salida).strip() == "" or str(fecha_salida).lower() == "none")
        
        if not es_activo:
            return False, None, "El colaborador ya no se encuentra activo en la empresa"
            
        return True, emp.get('Department'), "OK"
    except Exception as e:
        return False, None, f"Error de conexión: {str(e)}"

def save_response(data: dict):
    try:
        # Usamos upsert para manejar conflictos. 
        # Si la fecha es única en tu BD, esto actualizará el registro en lugar de fallar.
        supabase.table("encuestas").upsert(data).execute()
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "duplicate key" in error_msg:
            st.error("⚠️ Ya se registró una encuesta con esta marca de tiempo.")
        else:
            st.error(f"❌ Error al enviar: {e}")
        return False

# ==============================================================================
# 4. INTERFAZ DE USUARIO (FRONTEND)
# ==============================================================================

def main():
    if 'verified' not in st.session_state:
        st.session_state.update({'verified': False, 'emp_id': 0, 'emp_dept': ""})

    # --- CABECERA ---
    st.image("https://cdn-icons-png.flaticon.com/512/3593/3593461.png", width=80) # Icono genérico de encuesta
    st.title("Encuesta de Satisfacción")
    st.write("Tu opinión es fundamental para mejorar nuestro entorno de trabajo.")

    # --- CONFIGURACIÓN ACTUAL ---
    config = get_survey_config()
    is_global = config.get('encuesta_habilitada_global') == 'true'
    allowed_dept = config.get('departamento_habilitado', 'NINGUNO')

    # --- PASO 1: VALIDACIÓN ---
    if not st.session_state.verified:
        with st.container(border=True):
            st.subheader("🔑 Validación de Acceso")
            emp_id_input = st.number_input("Ingresa tu número de empleado:", min_value=1, step=1)
            
            if st.button("Verificar Identidad", type="secondary"):
                active, dept_eng, msg = get_employee_status(emp_id_input)
                
                if not active:
                    st.error(f"❌ {msg}")
                else:
                    # Validar si tiene permiso por área
                    if is_global or (dept_eng == allowed_dept):
                        st.session_state.update({
                            'verified': True,
                            'emp_id': emp_id_input,
                            'emp_dept': MAPEO_DEPTOS.get(dept_eng, dept_eng)
                        })
                        st.rerun()
                    else:
                        dept_esp = MAPEO_DEPTOS.get(allowed_dept, allowed_dept)
                        st.warning(f"🔒 Acceso restringido: Actualmente esta encuesta solo recibe respuestas del área de **{dept_esp}**.")

    # --- PASO 2: FORMULARIO ---
    else:
        # Banner de bienvenida
        st.markdown(f"""
            <div class="welcome-box">
                <b>¡Hola!</b> Identificación validada correctamente.<br>
                <b>ID:</b> {st.session_state.emp_id} | <b>Área:</b> {st.session_state.emp_dept}
            </div>
        """, unsafe_allow_html=True)

        with st.form("survey_form"):
            st.info("Responde con total sinceridad. Las respuestas son para fines de mejora interna.")
            
            # Bloques de preguntas
            col1, col2 = st.columns(2)
            with col1:
                env = st.select_slider("Ambiente de Trabajo", options=[1,2,3,4], value=3)
                inv = st.select_slider("Compromiso", options=[1,2,3,4], value=3)
                sat = st.select_slider("Satisfacción Tareas", options=[1,2,3,4], value=3)
                rel = st.select_slider("Relaciones Laborales", options=[1,2,3,4], value=3)
            with col2:
                wlb = st.select_slider("Equilibrio Vida/Trabajo", options=[1,2,3,4], value=3)
                per = st.select_slider("Intención de Permanencia", options=[1,2,3,4], value=3)
                conf = st.select_slider("Confianza en Dirección", options=[1,2,3,4], value=3)
            
            st.divider()
            carga = st.slider("Carga Laboral Percibida (1=Baja, 5=Muy Alta)", 1, 5, 3)
            pago = st.slider("Satisfacción Salarial (1=Baja, 5=Muy Alta)", 1, 5, 3)

            if st.form_submit_button("Enviar Encuesta", type="primary"):
                final_data = {
                    "EmployeeNumber": st.session_state.emp_id,
                    "EnvironmentSatisfaction": env,
                    "JobInvolvement": inv,
                    "JobSatisfaction": sat,
                    "RelationshipSatisfaction": rel,
                    "WorkLifeBalance": wlb,
                    "IntencionPermanencia": per,
                    "ConfianzaEmpresa": conf,
                    "CargaLaboralPercibida": carga,
                    "SatisfaccionSalarial": pago,
                    "Fecha": datetime.now().strftime('%Y-%m-%d')
                }
                
                if save_response(final_data):
                    st.balloons()
                    st.success("🎉 ¡Encuesta enviada exitosamente! Gracias por tu tiempo.")
                    st.session_state.verified = False
                    if st.button("Volver al inicio"): st.rerun()

        if st.button("Cerrar Sesión / Cancelar"):
            st.session_state.verified = False
            time.sleep(2) # Pausa breve para que vean el éxito
            st.rerun()

if __name__ == "__main__":
    main()