import streamlit as st
import pandas as pd
from supabase import create_client, Client

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS
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
# 2. FUNCIONES DE CONFIGURACIÓN
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

# =================================================================
# 3. INTERFAZ: PANEL DE CONTROL (ADMINISTRADOR)
# =================================================================

def render_survey_control_panel(supabase: Client):
    """
    Gestiona la habilitación de encuestas y muestra el link.
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔒 Control de Encuestas")

    config = get_survey_config(supabase)
    
    # --- 1. Control Global ---
    global_enabled_db = config.get('encuesta_habilitada_global', 'false') == 'true'
    global_enabled = st.sidebar.toggle("Habilitar para TODOS", value=global_enabled_db)
    
    if global_enabled != global_enabled_db:
        if update_survey_config(supabase, 'encuesta_habilitada_global', 'true' if global_enabled else 'false'):
            st.rerun()

    # --- 2. Control por Departamento ---
    # Usamos directamente las áreas del mapeo (sin consultar empleados activos)
    dept_options = ["NINGUNO (Deshabilitar)"] + list(MAPEO_DEPTOS.values())
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

    # --- 3. BLOQUE DEL LINK ---
    st.sidebar.markdown("---")
    st.sidebar.caption("🔗 Enlace de Encuesta Público")
    st.sidebar.code("https://encuestaimplementacion.streamlit.app/") 
    
    # Mensajes de Estado Visual
    if global_enabled:
        st.sidebar.success("Estado: ACTIVA para TODOS")
    elif selected_dept != "NINGUNO (Deshabilitar)":
        st.sidebar.warning(f"Estado: ACTIVA para {selected_dept}")
    else:
        st.sidebar.info("Estado: DESHABILITADA")

# =================================================================
# 4. EJECUCIÓN PRINCIPAL
# =================================================================

if __name__ == "__main__":
    render_survey_control_panel(supabase)
    
    st.title("Panel de Administración")
    st.write("Utiliza la barra lateral para gestionar la disponibilidad de la encuesta externa.")