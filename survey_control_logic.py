import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (Variables originales mantenidas)
# =================================================================

MAPEO_DEPTOS = {
    "Sales": "Ventas", 
    "Research & Development": "Investigación y Desarrollo", 
    "Human Resources": "Recursos Humanos"
}

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

def to_eng(mapeo, valor_esp):
    """Retorna la llave original (inglés) para la base de datos."""
    return [k for k, v in mapeo.items() if v == valor_esp][0]

# =================================================================
# 2. FUNCIONES DE BASE DE DATOS Y CONFIGURACIÓN
# =================================================================

@st.cache_data(ttl=1, hash_funcs={Client: lambda _: None})
def get_survey_config(supabase: Client):
    """Lee la tabla de configuración de la encuesta."""
    try:
        response = supabase.table("configuracion_encuesta").select("*").execute()
        return {item['clave']: item['valor'] for item in response.data}
    except Exception:
        return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}

def update_survey_config(supabase: Client, key: str, value: str):
    """Actualiza los parámetros de habilitación."""
    try:
        supabase.table("configuracion_encuesta").update({"valor": value}).eq("clave", key).execute()
        get_survey_config.clear()
        return True
    except Exception as e:
        st.error(f"Error al actualizar: {e}")
        return False

@st.cache_data(ttl=600, hash_funcs={Client: lambda _: None})
def fetch_departments_active(supabase: Client):
    """Obtiene áreas con empleados activos (FechaSalida es null)."""
    try:
        res = supabase.table("empleados").select("Department").is_("FechaSalida", "null").execute()
        depts_eng = set([d['Department'] for d in res.data if d['Department']])
        return sorted([MAPEO_DEPTOS.get(d, d) for d in depts_eng])
    except Exception:
        return []

# =================================================================
# 3. INTERFAZ: PANEL DE CONTROL (ADMINISTRADOR)
# =================================================================

def render_survey_control_panel(supabase: Client):
    """
    Gestiona la habilitación de encuestas. 
    Muestra áreas en español y permite decidir el alcance.
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔒 Control de Encuestas")

    config = get_survey_config(supabase)
    dept_list_esp = fetch_departments_active(supabase)
    
    # --- Control Global ---
    global_enabled_db = config.get('encuesta_habilitada_global', 'false') == 'true'
    global_enabled = st.sidebar.toggle("Habilitar para TODOS", value=global_enabled_db)
    
    if global_enabled != global_enabled_db:
        if update_survey_config(supabase, 'encuesta_habilitada_global', 'true' if global_enabled else 'false'):
            st.rerun()

    # --- Control por Departamento ---
    dept_options = ["NINGUNO (Deshabilitar)"] + dept_list_esp
    val_db_eng = config.get('departamento_habilitado', 'NINGUNO')
    val_actual_esp = MAPEO_DEPTOS.get(val_db_eng, "NINGUNO (Deshabilitar)")

    selected_dept = st.sidebar.selectbox(
        "Habilitar por Área específica:", 
        options=dept_options,
        index=dept_options.index(val_actual_esp) if val_actual_esp in dept_options else 0,
        disabled=global_enabled
    )
    
    if not global_enabled and selected_dept != val_actual_esp:
        val_to_save = to_eng(MAPEO_DEPTOS, selected_dept) if selected_dept != "NINGUNO (Deshabilitar)" else "NINGUNO"
        if update_survey_config(supabase, 'departamento_habilitado', val_to_save):
            st.rerun()

# =================================================================
# 4. INTERFAZ: VALIDACIÓN DE EMPLEADO (PARA LA ENCUESTA)
# =================================================================

def check_access_and_render_survey(supabase: Client):
    """
    Valida al empleado según el ID, que esté activo y pertenezca al área habilitada.
    """
    st.title("📋 Encuesta de Clima Organizacional")
    
    # Input de identificación
    emp_id = st.number_input("Ingrese su ID de Empleado", step=1, value=0)

    if st.button("Validar Acceso"):
        config = get_survey_config(supabase)
        is_global = config.get('encuesta_habilitada_global') == 'true'
        dept_allowed = config.get('departamento_habilitado', 'NINGUNO')

        # 1. ¿Está abierta la encuesta?
        if not is_global and dept_allowed == "NINGUNO":
            st.error("🚫 La encuesta se encuentra cerrada actualmente.")
            return

        # 2. ¿Existe el empleado y está activo?
        res = supabase.table("empleados")\
            .select("Department")\
            .eq("EmployeeNumber", emp_id)\
            .is_("FechaSalida", "null")\
            .execute()

        if not res.data:
            st.error("❌ Acceso denegado: ID no encontrado o colaborador inactivo.")
            return

        # 3. ¿Pertenece al área correcta?
        emp_dept = res.data[0]['Department']
        
        if is_global or emp_dept == dept_allowed:
            st.success("✅ Acceso concedido. Cargando formulario...")
            st.session_state.survey_auth = True
            st.session_state.current_user_id = emp_id
            # Aquí se procedería a mostrar la encuesta
        else:
            area_esp = MAPEO_DEPTOS.get(dept_allowed, dept_allowed)
            st.warning(f"⚠️ Esta etapa es exclusiva para el área de: {area_esp}.")

# =================================================================
# 5. EJECUCIÓN PRINCIPAL
# =================================================================

if __name__ == "__main__":
    # Renderizar panel lateral de administración
    render_survey_control_panel(supabase)
    
    # Lógica de la página de encuesta
    if "survey_auth" not in st.session_state:
        check_access_and_render_survey(supabase)
    else:
        st.write(f"### Bienvenido, Colaborador ID: {st.session_state.current_user_id}")
        if st.button("Finalizar Sesión"):
            del st.session_state.survey_auth
            st.rerun()