import streamlit as st
from supabase import Client
from typing import Optional

# NOTA: Asegúrate de que el cliente 'supabase' se defina en 'app.py' y se pase como argumento.

# ==============================================================================
# 1. FUNCIONES DE CONFIGURACIÓN (CRUD)
# ==============================================================================

def update_survey_config(supabase: Client, key: str, value: str):
    """Actualiza un valor en la tabla 'configuracion_encuesta' de Supabase."""
    if supabase is None: 
        st.error("Error de conexión a Supabase.")
        return False
    try:
        # Escribe la nueva configuración en la BD
        supabase.table("configuracion_encuesta").update({"valor": value}) \
            .eq("clave", key) \
            .execute()
        st.toast(f"✅ Configuración '{key}' actualizada a: {value}")
        return True
    except Exception as e:
        st.error(f"Error al actualizar la configuración: {e}")
        return False

@st.cache_data(ttl=1)
def get_survey_config(supabase: Client):
    """Obtiene el estado de la configuración de la encuesta desde Supabase."""
    if supabase is None: return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}
    try:
        response = supabase.table("configuracion_encuesta").select("*").execute()
        # Mapea la lista de diccionarios a un solo diccionario clave:valor
        return {item['clave']: item['valor'] for item in response.data}
    except Exception as e:
        st.error(f"Error al obtener configuración: {e}")
        return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}

@st.cache_data(ttl=600)
def fetch_departments(supabase: Client):
    """Obtiene la lista única de departamentos para el selector de control."""
    if supabase is None: return []
    try:
        # Se asume que la tabla principal que contiene los departamentos es 'empleados'
        response = supabase.table("empleados").select("Department").distinct().execute()
        return [d['Department'] for d in response.data]
    except Exception:
        return []

# ==============================================================================
# 2. PANEL DE CONTROL DE ENCUESTAS (Renderizado para app.py)
# ==============================================================================

def render_survey_control_panel(supabase: Client):
    """Renderiza el panel de control que habilita/inhabilita la encuesta (ADMIN)."""
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔒 Control de Encuestas (Link Público)")

    config = get_survey_config(supabase)
    dept_list = fetch_departments(supabase)
    
    # --- 1. Control Global ---
    global_enabled_db = config.get('encuesta_habilitada_global', 'false') == 'true'
    global_enabled = st.sidebar.checkbox(
        "1. Habilitar Globalmente (Para TODOS)", 
        value=global_enabled_db,
        key="global_survey_toggle"
    )
    if global_enabled != global_enabled_db:
        update_survey_config(supabase, 'encuesta_habilitada_global', 'true' if global_enabled else 'false')

    # --- 2. Control por Área ---
    dept_options = ["NINGUNO (Deshabilitar)", "TODOS (Global)"] + sorted(dept_list)
    
    selected_dept_db = config.get('departamento_habilitado', 'NINGUNO')
    selected_dept = st.sidebar.selectbox(
        "2. Habilitar por Departamento:", 
        options=dept_options,
        index=dept_options.index(selected_dept_db) if selected_dept_db in dept_options else 0,
        key="dept_survey_select"
    )
    if selected_dept != selected_dept_db:
        update_survey_config(supabase, 'departamento_habilitado', selected_dept)

    # --- Mensajes de Estado ---
    st.sidebar.markdown("---")
    st.sidebar.caption("🔗 Enlace de Encuesta Público")
    st.sidebar.code("https://encuestaimplementacion.streamlit.app/") 
    
    if global_enabled:
        st.sidebar.success("Estado: ACTIVA para TODOS.")
    elif selected_dept != "NINGUNO (Deshabilitar)":
        st.sidebar.warning(f"Estado: ACTIVA SÓLO para {selected_dept}")
    else:
        st.sidebar.info("Estado: DESHABILITADA TOTALMENTE.")