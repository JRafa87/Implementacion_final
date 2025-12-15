import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re
import pytz

# Configuración de la Zona Horaria de Perú
TIMEZONE_PERU = pytz.timezone('America/Lima')

# --- Inicialización de st.session_state (ASEGÚRATE DE QUE SE EJECUTE) ---

if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
    st.session_state["full_name"] = ""
    st.session_state["date_of_birth"] = None 
    st.session_state["phone_number"] = ""
    st.session_state["address"] = ""
    st.session_state["avatar_image"] = None 
    st.session_state["avatar_url"] = None 
    st.session_state["user_email"] = "N/A"
    st.session_state["user_role"] = "guest"
    st.session_state["created_at"] = None 
    st.session_state["last_sign_in_at"] = None
    st.session_state["temp_avatar_bytes"] = None
    st.session_state["profile_loaded"] = False 
# NOTA: Los errores de validación se manejan localmente en el formulario para evitar el bug de Streamlit

# ====================================================================
# === 1. FUNCIONES DE CONEXIÓN Y CARGA (USA EL CLIENTE PROPORCIONADO) ===
# ====================================================================

@st.cache_data(ttl=600)
def load_user_profile_data(user_id, supabase_client):
    """
    Busca los datos en la tabla 'profiles' de Supabase y los retorna.
    """
    if not user_id:
        return None

    try:
        # Consulta a la tabla 'profiles'
        # Si la fila no existe, la función fallará. Es crucial manejar esto.
        response = supabase_client.table('profiles').select('*').eq('id', user_id).single().execute()
        return response.data
        
    except Exception as e:
        # Esto captura errores comunes de Supabase (ej: 'Row not found')
        # Es necesario que tu lógica principal cree el perfil si este no existe.
        st.warning(f"⚠️ Error al cargar el perfil para ID {user_id}. Verifique si el registro existe en 'profiles'. Error: {e}")
        return None

def update_session_state_from_profile(profile_data):
    """Carga los datos obtenidos de la BD al estado de la sesión."""
    if profile_data:
        st.session_state["full_name"] = profile_data.get("full_name", "")
        st.session_state["phone_number"] = profile_data.get("phone_number", "")
        st.session_state["address"] = profile_data.get("address", "")
        st.session_state["date_of_birth"] = profile_data.get("date_of_birth") 
        st.session_state["avatar_url"] = profile_data.get("avatar_url")
        st.session_state["user_role"] = profile_data.get("role", "member")
        
        # 🛑 CAPTURA DE LA FECHA DE CREACIÓN 🛑
        st.session_state["created_at"] = profile_data.get("created_at")
        
        st.session_state["profile_loaded"] = True
    else:
        st.session_state["profile_loaded"] = False


# ====================================================================
# === 2. FUNCIONES AUXILIARES (Formateo y Callbacks) ===
# ====================================================================

def handle_file_upload():
    """Maneja la subida de un archivo y guarda los bytes temporalmente."""
    uploaded_file = st.session_state.get("avatar_uploader_widget")
    
    if uploaded_file is not None:
        uploaded_file.seek(0)
        new_avatar_bytes = uploaded_file.read()
        st.session_state["temp_avatar_bytes"] = new_avatar_bytes 
        
        if "avatar_image" in st.session_state: del st.session_state["avatar_image"]
        if "avatar_url" in st.session_state: del st.session_state["avatar_url"]


def format_iso_date(iso_string, use_current_time_if_none=False, date_only=False):
    """Formatea un string ISO 8601 a un formato legible en la zona horaria de Perú."""
    
    if not iso_string:
        if use_current_time_if_none:
            now_peru = datetime.datetime.now(TIMEZONE_PERU)
            format_str = "%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M hrs (PE)"
            return now_peru.strftime(format_str)
        else:
            return "N/A (No cargado)"
            
    try:
        dt_utc = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        dt_peru = dt_utc.astimezone(TIMEZONE_PERU)
        
        if date_only:
            return dt_peru.strftime("%Y-%m-%d")
        else:
            return dt_peru.strftime("%Y-%m-%d %H:%M hrs (PE)")
            
    except (ValueError, TypeError):
        return "N/A (Error de formato)"


# --- FUNCIÓN DE ACTUALIZACIÓN ---
def update_user_profile(new_name: str, new_dob: datetime.date, new_phone: str, new_address: str, avatar_bytes: Optional[bytes], user_id: str, supabase_client):
    """Función principal que actualiza los datos del perfil en Supabase."""
    data_to_update = {}

    # Si hay errores pendientes (esto se maneja en el form, pero es una seguridad)
    if st.session_state.get("name_error") or st.session_state.get("phone_error"):
        st.error("❌ Por favor, corrige los errores de validación antes de guardar.")
        return

    # ... (Lógica de detección de cambios y preparación de data_to_update) ...
    if new_name != st.session_state.get("full_name"): data_to_update["full_name"] = new_name
    if new_phone != st.session_state.get("phone_number"): data_to_update["phone_number"] = new_phone
    if new_address != st.session_state.get("address"): data_to_update["address"] = new_address
    dob_str = new_dob.strftime("%Y-%m-%d") if new_dob else None
    current_dob_str = st.session_state.get("date_of_birth")
    if dob_str != current_dob_str: data_to_update["date_of_birth"] = dob_str 

    # Manejo del Avatar:
    if avatar_bytes is not None and avatar_bytes != st.session_state.get("avatar_image"):
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        data_to_update["avatar_url"] = avatar_base64
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        data_to_update["avatar_url"] = None

    if data_to_update:
        try:
            # --- LÓGICA REAL DE SUPABASE. ---
            supabase_client.table("profiles").update(data_to_update).eq("id", user_id).execute()
            
            # --- Actualización del estado local y limpieza de caché ---
            st.session_state.update({k: v for k, v in data_to_update.items()})
            if avatar_bytes is not None:
                 st.session_state["avatar_image"] = avatar_bytes 
            
            if "temp_avatar_bytes" in st.session_state:
                del st.session_state["temp_avatar_bytes"]
                
            # Limpiar la caché para que la próxima carga traiga los datos recién guardados
            load_user_profile_data.clear() 
            
            st.success("✅ ¡Perfil actualizado con éxito!")
            time.sleep(1) 
            st.rerun() 
            
        except Exception as e:
            st.error(f"❌ Error al actualizar el perfil: {e}")
    else:
        st.info("ℹ️ No se detectaron cambios para guardar.")


# ====================================================================
# === 3. RENDERIZADO PRINCIPAL ===
# ====================================================================

def render_profile_page(supabase_client, request_password_reset_callback):
    """Renderiza el perfil del usuario."""
    user_id = st.session_state.get("user_id")
    
    # 1. Cargar el perfil (se ejecuta solo si no ha sido cargado en el estado)
    if not st.session_state.get("profile_loaded") and user_id:
        with st.spinner("Cargando datos del perfil..."):
            profile_data = load_user_profile_data(user_id, supabase_client)
            update_session_state_from_profile(profile_data)
            
            # Forzar un rerun si los datos se acaban de cargar
            if st.session_state.get("profile_loaded"):
                 st.rerun() 
                 
    # Obtener valores actuales (se ejecuta después del rerun si fue necesario)
    current_name = st.session_state.get("full_name", "")
    current_dob_str = st.session_state.get("date_of_birth")
    current_phone = st.session_state.get("phone_number", "") 
    current_address = st.session_state.get("address", "")
    
    # ... (variables de avatar) ...

    if not user_id or not st.session_state.get("profile_loaded"):
        st.warning("⚠️ Perfil no cargado o usuario no autenticado. Por favor, inicie sesión.")
        return

    col_avatar, col_details = st.columns([1, 2])

    with col_details:
        st.header("Datos Personales y de Cuenta")
        
        with st.form("profile_form", clear_on_submit=False):
            
            # ... (código del avatar) ...
            with col_avatar:
                st.subheader("Foto de Perfil")
                # Lógica de display del avatar
                display_image = st.session_state.get("temp_avatar_bytes") or st.session_state.get("avatar_image") or st.session_state.get("avatar_url", "https://placehold.co/200x200/A0A0A0/ffffff?text=U")
                st.image(display_image, width=150)
                
                st.file_uploader("Subir/Cambiar Foto", type=["png","jpg","jpeg"], key="avatar_uploader_widget", on_change=handle_file_upload)
                
                if st.session_state.get("temp_avatar_bytes") is not None or st.session_state.get("avatar_url") is not None:
                    if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar."):
                        st.session_state["temp_avatar_bytes"] = None 
                        st.session_state["avatar_image"] = None
                        st.session_state["avatar_url"] = None
                        st.rerun() 
                        
            # Banderas de error locales (CONTROLAN EL BOTÓN DE FORMA INMEDIATA)
            local_name_error = False
            local_phone_error = False
                        
            # --- INPUT: Nombre y Validación (SOLUCIÓN AL NO ACTUALIZARSE) ---
            new_name = st.text_input("👤 Nombre completo", value=current_name, key="new_name")
            
            name_pattern = r"^[A-Za-zñÑáéíóúÁÉÍÓÚ\s]+$"
            if new_name and not re.match(name_pattern, new_name):
                st.error("❌ Error: El nombre no puede contener números ni caracteres especiales.")
                local_name_error = True

            # --- INPUT: Teléfono y Validación (SOLUCIÓN AL NO ACTUALIZARSE) ---
            new_phone = st.text_input("📞 Teléfono de contacto (9 dígitos, inicia con 9)", value=current_phone, max_chars=9, key="new_phone")

            if new_phone and not re.match(r"^9\d{8}$", new_phone):
                   st.error("❌ Error: El teléfono debe comenzar con '9' y contener exactamente 9 dígitos.")
                   local_phone_error = True
            
            # Determinamos si el botón debe estar deshabilitado
            submit_button_disabled = local_name_error or local_phone_error 

            # Actualizamos el estado de sesión para el chequeo final de update_user_profile
            st.session_state["name_error"] = local_name_error
            st.session_state["phone_error"] = local_phone_error

            # --- INPUTS RESTANTES ---
            dob_value = None
            if current_dob_str:
                try:
                    dob_value = datetime.datetime.strptime(current_dob_str, "%Y-%m-%d").date()
                except (ValueError, TypeError): pass
            
            new_dob = st.date_input("🗓️ Fecha de nacimiento", value=dob_value or datetime.date(2000, 1, 1), min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today(), key="new_dob")
            new_address = st.text_area("🏠 Dirección (Opcional)", value=current_address, key="new_address")

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            
            # 1. Fecha de Creación (Jalada de la BD y formateada a solo fecha de Perú)
            formatted_created = format_iso_date(st.session_state.get("created_at"), date_only=True)
            # 2. Último Acceso (Asumido de Auth y formateado a fecha y hora de Perú)
            formatted_last_access = format_iso_date(st.session_state.get("last_sign_in_at"), use_current_time_if_none=True, date_only=False)

            col_left, col_right = st.columns(2)
            with col_left:
                st.text_input("📅 Fecha de Creación", value=formatted_created, disabled=True, 
                              help="Momento en que el perfil fue creado en la tabla 'profiles'.")
            with col_right:
                st.text_input("⏰ Último Acceso", value=formatted_last_access, disabled=True,
                              help="Última vez que el usuario inició sesión. Hora ajustada a Perú (PE).")
            
            st.text_input("🏷️ Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("📧 Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Botón de Guardar
            if st.form_submit_button("💾 Guardar Cambios", disabled=submit_button_disabled):
                
                final_avatar_bytes = st.session_state.get("temp_avatar_bytes") or st.session_state.get("avatar_image")
                
                update_user_profile(
                    new_name, new_dob, new_phone, new_address, final_avatar_bytes, user_id, supabase_client 
                )

    # Botón de cambio de contraseña fuera del form
    st.markdown("---")
    if st.button("🔒 Cambiar Contraseña", use_container_width=True):
        request_password_reset_callback(st.session_state.get("user_email"))



