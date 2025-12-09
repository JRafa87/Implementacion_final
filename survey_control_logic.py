import streamlit as st
from supabase import Client
from typing import Optional

# NOTA: Asegúrate de que el cliente 'supabase' se defina en 'app.py' y se pase como argumento.

# ==============================================================================
# 1. FUNCIONES DE CONFIGURACIÓN (CRUD)
# ==============================================================================

# Añadir la invalidación de caché para que los cambios se reflejen
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
        
        # 💡 CORRECCIÓN/MEJORA: Invalidar la caché para forzar la re-lectura inmediata
        get_survey_config.clear()
        
        return True
    except Exception as e:
        st.error(f"Error al actualizar la configuración: {e}")
        return False

# 💡 CORRECCIÓN: Se añade hash_funcs para que el objeto Client sea hasheable
@st.cache_data(ttl=1, hash_funcs={Client: lambda _: None})
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

# 💡 CORRECCIÓN: Se añade hash_funcs para que el objeto Client sea hasheable
@st.cache_data(ttl=600, hash_funcs={Client: lambda _: None})
def fetch_departments(supabase: Client):
    """Obtiene la lista única de departamentos para el selector de control."""
    if supabase is None: return []
    try:
        # Se asume que la tabla principal que contiene los departamentos es 'empleados'
        response = supabase.table("empleados").select("Department").distinct().execute()
        
        # Filtrar valores nulos o vacíos que puedan venir de la BD
        return sorted([d['Department'] for d in response.data if d['Department']])
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
        if update_survey_config(supabase, 'encuesta_habilitada_global', 'true' if global_enabled else 'false'):
            st.rerun() # 💡 MEJORA: Forzar rerun tras cambio global

    # --- 2. Control por Área ---
    # 💡 MEJORA: Se eliminó la opción "TODOS (Global)" por ser redundante con el checkbox
    dept_options = ["NINGUNO (Deshabilitar)"] + dept_list 
    
    selected_dept_db = config.get('departamento_habilitado', 'NINGUNO')
    
    # Manejar el caso donde el valor guardado ya no está en la lista de opciones (ej: "TODOS (Global)")
    current_index = 0
    if selected_dept_db in dept_options:
        current_index = dept_options.index(selected_dept_db)

    selected_dept = st.sidebar.selectbox(
        "2. Habilitar por Departamento:", 
        options=dept_options,
        index=current_index,
        disabled=global_enabled, # 💡 MEJORA: Deshabilitar si el global está activo
        key="dept_survey_select"
    )
    
    if selected_dept != selected_dept_db:
        if update_survey_config(supabase, 'departamento_habilitado', selected_dept):
            st.rerun() # 💡 MEJORA: Forzar rerun tras cambio de departamento

    # --- Mensajes de Estado ---
    st.sidebar.markdown("---")
    st.sidebar.caption("🔗 Enlace de Encuesta Público")
    st.sidebar.code("https://encuestaimplementacion.streamlit.app/") 
    
    if global_enabled:
        st.sidebar.success("Estado: ACTIVA para TODOS (Prioridad Global).")
    elif selected_dept != "NINGUNO (Deshabilitar)":
        st.sidebar.warning(f"Estado: ACTIVA SÓLO para **{selected_dept}**")
    else:
        st.sidebar.info("Estado: DESHABILITADA TOTALMENTE.")