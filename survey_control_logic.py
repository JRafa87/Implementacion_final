import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN, MAPEOS Y CLIENTE
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
    """Retorna la llave en inglés dado el valor en español."""
    return [k for k, v in mapeo.items() if v == valor_esp][0]

# =================================================================
# 2. FUNCIONES DE BASE DE DATOS (CONFIGURACIÓN)
# =================================================================

@st.cache_data(ttl=1, hash_funcs={Client: lambda _: None})
def get_survey_config(supabase: Client):
    """Obtiene el estado de la configuración de la encuesta."""
    try:
        response = supabase.table("configuracion_encuesta").select("*").execute()
        return {item['clave']: item['valor'] for item in response.data}
    except Exception as e:
        st.error(f"Error al obtener configuración: {e}")
        return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}

def update_survey_config(supabase: Client, key: str, value: str):
    """Actualiza la configuración e invalida la caché."""
    try:
        supabase.table("configuracion_encuesta").update({"valor": value}).eq("clave", key).execute()
        get_survey_config.clear()
        st.toast(f"✅ Configuración '{key}' actualizada")
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

@st.cache_data(ttl=600, hash_funcs={Client: lambda _: None})
def fetch_departments_active(supabase: Client):
    """Obtiene solo departamentos con empleados activos y los traduce."""
    try:
        # Consultamos empleados donde FechaSalida es NULL (Activos)
        response = supabase.table("empleados").select("Department").is_("FechaSalida", "null").execute()
        depts_eng = set([d['Department'] for d in response.data if d['Department']])
        # Traducir a español usando el mapa
        return sorted([MAPEO_DEPTOS.get(d, d) for d in depts_eng])
    except Exception:
        return []

# =================================================================
# 3. PANEL DE CONTROL (ADMIN)
# =================================================================

def render_survey_control_panel(supabase: Client):
    """Panel para habilitar/deshabilitar encuestas por área o global."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔒 Control de Encuestas")

    config = get_survey_config(supabase)
    dept_list_esp = fetch_departments_active(supabase)
    
    # --- 1. Control Global ---
    global_enabled_db = config.get('encuesta_habilitada_global', 'false') == 'true'
    global_enabled = st.sidebar.checkbox(
        "Habilitar Globalmente (Para TODOS)", 
        value=global_enabled_db,
        key="global_survey_toggle"
    )
    
    if global_enabled != global_enabled_db:
        if update_survey_config(supabase, 'encuesta_habilitada_global', 'true' if global_enabled else 'false'):
            st.rerun()

    # --- 2. Control por Departamento (En Español) ---
    dept_options = ["NINGUNO (Deshabilitar)"] + dept_list_esp
    
    # Traducimos lo que viene de la DB (Inglés) a Español para el selector
    val_db_eng = config.get('departamento_habilitado', 'NINGUNO')
    val_actual_esp = MAPEO_DEPTOS.get(val_db_eng, val_db_eng) if val_db_eng != 'NINGUNO' else "NINGUNO (Deshabilitar)"

    selected_dept_esp = st.sidebar.selectbox(
        "Habilitar por Departamento:", 
        options=dept_options,
        index=dept_options.index(val_actual_esp) if val_actual_esp in dept_options else 0,
        disabled=global_enabled,
        key="dept_survey_select"
    )
    
    if selected_dept_esp != val_actual_esp:
        # Convertimos de vuelta a inglés para guardar en la base de datos
        val_to_save = "NINGUNO"
        if selected_dept_esp != "NINGUNO (Deshabilitar)":
            val_to_save = to_eng(MAPEO_DEPTOS, selected_dept_esp)
            
        if update_survey_config(supabase, 'departamento_habilitado', val_to_save):
            st.rerun()

    # --- Estados visuales ---
    if global_enabled:
        st.sidebar.success("Estado: ACTIVA GLOBALMENTE")
    elif selected_dept_esp != "NINGUNO (Deshabilitar)":
        st.sidebar.warning(f"Estado: ACTIVA para {selected_dept_esp}")
    else:
        st.sidebar.info("Estado: DESHABILITADA")

# =================================================================
# 4. LÓGICA DE VALIDACIÓN PARA EL EMPLEADO (LINK PÚBLICO)
# =================================================================

def check_employee_access(supabase: Client, employee_id: int):
    """
    Verifica si el ID ingresado pertenece a un empleado activo 
    y si su departamento tiene la encuesta permitida.
    """
    config = get_survey_config(supabase)
    global_on = config.get('encuesta_habilitada_global', 'false') == 'true'
    dept_allowed_eng = config.get('departamento_habilitado', 'NINGUNO')

    if not global_on and dept_allowed_eng == 'NINGUNO':
        return False, "La encuesta no está disponible en este momento."

    try:
        # Buscamos al empleado: que coincida el ID y que no tenga fecha de salida
        res = supabase.table("empleados")\
            .select("Department")\
            .eq("EmployeeNumber", employee_id)\
            .is_("FechaSalida", "null")\
            .execute()

        if not res.data:
            return False, "ID no encontrado o el empleado ya no está activo."

        depto_empleado = res.data[0]['Department']

        if global_on:
            return True, "Acceso concedido."
        
        if depto_empleado == dept_allowed_eng:
            return True, "Acceso concedido para su departamento."
        else:
            depto_esp = MAPEO_DEPTOS.get(dept_allowed_eng, dept_allowed_eng)
            return False, f"Esta encuesta solo está habilitada para el área de {depto_esp}."

    except Exception as e:
        return False, f"Error de conexión: {e}"

# Ejemplo de uso en la App
if __name__ == "__main__":
    # Esto renderiza el panel lateral
    render_survey_control_panel(supabase)
    
    # Ejemplo de validación en el cuerpo de la página
    st.title("Encuesta de Clima")
    emp_id = st.number_input("Ingrese su ID de Empleado", step=1)
    if st.button("Validar Acceso"):
        valido, msg = check_employee_access(supabase, emp_id)
        if valido:
            st.success(msg)
            # Aquí iría el resto de tu encuesta
        else:
            st.error(msg)