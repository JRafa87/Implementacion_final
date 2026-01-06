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
# 2. FUNCIONES DE CONFIGURACIÓN (CRUD LIGERO)
# =================================================================

@st.cache_data(ttl=1)
def get_survey_config(supabase: Client):
    """Obtiene el estado actual de la configuración de la encuesta."""
    try:
        response = supabase.table("configuracion_encuesta").select("*").execute()
        return {item['clave']: item['valor'] for item in response.data}
    except Exception:
        return {'encuesta_habilitada_global': 'false', 'departamento_habilitado': 'NINGUNO'}

def update_survey_config(supabase: Client, key: str, value: str):
    """Actualiza la configuración e invalida caché para cambios inmediatos."""
    try:
        supabase.table("configuracion_encuesta").update({"valor": value}).eq("clave", key).execute()
        get_survey_config.clear()
        st.toast(f"✅ Configuración '{key}' actualizada.")
        return True
    except Exception as e:
        st.error(f"Error al actualizar: {e}")
        return False

# =================================================================
# 3. PANEL DE CONTROL (ADMINISTRADOR)
# =================================================================

def render_survey_control_panel(supabase: Client):
    """Renderiza el panel de control lateral con el enlace público."""
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔒 Control de Encuestas (Link Público)")

    config = get_survey_config(supabase)
    
    # --- 1. Control Global ---
    global_enabled_db = config.get('encuesta_habilitada_global', 'false') == 'true'
    global_enabled = st.sidebar.checkbox(
        "1. Habilitar Globalmente (Para TODOS)", 
        value=global_enabled_db,
        key="global_survey_toggle"
    )
    
    if global_enabled != global_enabled_db:
        if update_survey_config(supabase, 'encuesta_habilitada_global', 'true' if global_enabled else 'false'):
            st.rerun()

    # --- 2. Control por Área ---
    # Mostramos las opciones en español basadas en tu MAPEO_DEPTOS
    dept_options = ["NINGUNO (Deshabilitar)"] + list(MAPEO_DEPTOS.values())
    
    val_db_eng = config.get('departamento_habilitado', 'NINGUNO')
    val_actual_esp = MAPEO_DEPTOS.get(val_db_eng, "NINGUNO (Deshabilitar)")

    selected_dept = st.sidebar.selectbox(
        "2. Habilitar por Departamento:", 
        options=dept_options,
        index=dept_options.index(val_actual_esp) if val_actual_esp in dept_options else 0,
        disabled=global_enabled,
        key="dept_survey_select"
    )
    
    if not global_enabled and selected_dept != val_actual_esp:
        # Convertimos a inglés antes de guardar para que la encuesta pueda validar
        val_to_save = "NINGUNO"
        if selected_dept != "NINGUNO (Deshabilitar)":
            val_to_save = to_eng(MAPEO_DEPTOS, selected_dept)
            
        if update_survey_config(supabase, 'departamento_habilitado', val_to_save):
            st.rerun()

    # --- 3. Enlace Público (Reintegrado exactamente como antes) ---
    st.sidebar.markdown("---")
    st.sidebar.caption("🔗 Enlace de Encuesta Público")
    # Este es el link que los administradores copian para enviar a los empleados
    st.sidebar.code("https://encuestaimplementacion.streamlit.app/") 
    
    # Mensajes de Estado Dinámicos
    if global_enabled:
        st.sidebar.success("Estado: ACTIVA para TODOS (Prioridad Global).")
    elif selected_dept != "NINGUNO (Deshabilitar)":
        st.sidebar.warning(f"Estado: ACTIVA SÓLO para **{selected_dept}**")
    else:
        st.sidebar.info("Estado: DESHABILITADA TOTALMENTE.")

# =================================================================
# 4. PUNTO DE ENTRADA
# =================================================================

if __name__ == "__main__":
    # Inyectar el panel en la sidebar de la aplicación principal
    render_survey_control_panel(supabase)
    
    st.title("Panel de Gestión Administrativa")
    st.write("Bienvenido al centro de mando. Usa la barra lateral para abrir o cerrar el acceso a la encuesta pública.")