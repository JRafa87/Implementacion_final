import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re
import pytz # Importamos la librería de zona horaria

# Configuración de la Zona Horaria de Perú
TIMEZONE_PERU = pytz.timezone('America/Lima')

# -------------------------------------------------------------------
# --- Inicialización de st.session_state ---
# -------------------------------------------------------------------

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
    # El valor de created_at DEBE ser un string ISO 8601 cargado desde Supabase.
    st.session_state["created_at"] = None 
    st.session_state["last_sign_in_at"] = None
    st.session_state["temp_avatar_bytes"] = None
    st.session_state["name_error"] = False
    st.session_state["phone_error"] = False


# ====================================================================
# === 1. FUNCIONES AUXILIARES (Formateo y Callbacks) ===
# ====================================================================

def handle_file_upload():
    """Maneja la subida de un archivo y guarda los bytes temporalmente."""
    uploaded_file = st.session_state.get("avatar_uploader_widget")
    
    if uploaded_file is not None:
        uploaded_file.seek(0)
        new_avatar_bytes = uploaded_file.read()
        st.session_state["temp_avatar_bytes"] = new_avatar_bytes 
        
        if "avatar_image" in st.session_state:
            del st.session_state["avatar_image"]
        if "avatar_url" in st.session_state:
            del st.session_state["avatar_url"]
        
        # Necesitamos un rerun para que el widget de imagen se actualice inmediatamente
        # st.rerun() # Esto puede ser agresivo si no es necesario en tu layout, pero asegura la visualización

        
def format_iso_date(iso_string, use_current_time_if_none=False, date_only=False):
    """
    Formatea un string ISO 8601 de Supabase a un formato legible en la zona horaria de Perú.
    """
    
    if not iso_string:
        if use_current_time_if_none:
            # Si no hay string, usa la hora actual del sistema, forzando la zona horaria de Perú
            now_peru = datetime.datetime.now(TIMEZONE_PERU)
            format_str = "%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M hrs (PE)"
            return now_peru.strftime(format_str)
        else:
            return "N/A (No cargado)"
            
    try:
        # 1. Parsear el string ISO (maneja la 'Z' de UTC)
        dt_utc = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        
        # 2. Convertir la hora de UTC a la Zona Horaria de Perú
        dt_peru = dt_utc.astimezone(TIMEZONE_PERU)
        
        # 3. Aplicamos el formato deseado
        if date_only:
            return dt_peru.strftime("%Y-%m-%d")
        else:
            return dt_peru.strftime("%Y-%m-%d %H:%M hrs (PE)")
            
    except (ValueError, TypeError):
        return "N/A (Error de formato)"


# --- FUNCIÓN DE ACTUALIZACIÓN ---
def update_user_profile(new_name: str, new_dob: datetime.date, new_phone: str, new_address: str, avatar_bytes: Optional[bytes], user_id: str, supabase):
    """
    Función principal que intenta actualizar los datos del perfil en Supabase.
    """
    data_to_update = {}

    # Si hay errores en el estado, se impide el guardado
    if st.session_state.get("name_error") or st.session_state.get("phone_error"):
        st.error("❌ Por favor, corrige los errores de validación antes de guardar.")
        return

    # ... (Lógica de detección de cambios y preparación de data_to_update) ...

    # 1. Nombre
    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name
    # 2. Teléfono
    if new_phone != st.session_state.get("phone_number"):
        data_to_update["phone_number"] = new_phone
    # 3. Dirección
    if new_address != st.session_state.get("address"):
        data_to_update["address"] = new_address
    # 4. Fecha de nacimiento
    dob_str = new_dob.strftime("%Y-%m-%d") if new_dob else None
    current_dob_str = st.session_state.get("date_of_birth")
    if dob_str != current_dob_str:
        data_to_update["date_of_birth"] = dob_str 
    # 5. Manejo del Avatar:
    if avatar_bytes is not None and avatar_bytes != st.session_state.get("avatar_image"):
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        data_to_update["avatar_url"] = avatar_base64
        st.session_state["avatar_image"] = avatar_bytes 
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        data_to_update["avatar_url"] = None
        st.session_state["avatar_image"] = None 


    if data_to_update:
        try:
            # --- Aquí iría la lógica REAL de Supabase.update() ---
            # result = supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            
            # Actualización del estado (simulación de éxito)
            st.session_state.update({k: v for k, v in data_to_update.items()})
            
            if "temp_avatar_bytes" in st.session_state:
                del st.session_state["temp_avatar_bytes"]
            
            st.success("✅ ¡Perfil actualizado con éxito!")
            time.sleep(1) 
            st.rerun() 
            
        except Exception as e:
            st.error(f"❌ Error al actualizar el perfil: {e}")
    else:
        st.info("ℹ️ No se detectaron cambios para guardar.")


# ====================================================================
# === 2. RENDERIZADO PRINCIPAL ===
# ====================================================================

def render_profile_page(supabase_client, request_password_reset_callback):
    """Renderiza el perfil del usuario con validaciones de entrada."""
    user_id = st.session_state.get("user_id")
    
    # ----------------------------------------------------------------
    # 🛑 NOTA IMPORTANTE PARA CARGA DE DATOS:
    # Asegúrate de que tu lógica de login/carga de perfil ejecute una consulta
    # a la tabla 'profiles' para obtener y guardar en el estado:
    # st.session_state["created_at"] = <El valor de profiles.created_at en ISO string>
    # ----------------------------------------------------------------

    current_name = st.session_state.get("full_name", "")
    current_dob_str = st.session_state.get("date_of_birth")
    current_phone = st.session_state.get("phone_number", "") 
    current_address = st.session_state.get("address", "")
    avatar_bytes_saved = st.session_state.get("avatar_image")
    avatar_url = st.session_state.get("avatar_url", None)
    temp_bytes = st.session_state.get("temp_avatar_bytes")

    if not user_id:
        st.warning("⚠️ No se pudo cargar el ID del usuario. Por favor, asegúrate de haber iniciado sesión y cargado el perfil.")
        return

    col_avatar, col_details = st.columns([1, 2])

    with col_details:
        st.header("Datos Personales y de Cuenta")
        
        # Banderas de error iniciales (se reevalúan en los inputs)
        st.session_state["name_error"] = False
        st.session_state["phone_error"] = False

        with st.form("profile_form", clear_on_submit=False):
            
            # --- Manejo de la Foto de Perfil (Columna Izquierda) ---
            with col_avatar:
                st.subheader("Foto de Perfil")
                
                # Lógica de display del avatar
                if temp_bytes is not None:
                    display_image = temp_bytes 
                elif avatar_bytes_saved is not None:
                    display_image = avatar_bytes_saved
                elif avatar_url is not None:
                    display_image = avatar_url
                else:
                    display_image = "https://placehold.co/200x200/A0A0A0/ffffff?text=U"
                        
                st.image(display_image, width=150)
                
                # Uploader
                st.file_uploader(
                    "Subir/Cambiar Foto", 
                    type=["png","jpg","jpeg"], 
                    key="avatar_uploader_widget", 
                    on_change=handle_file_upload 
                )
                
                # Opción para Quitar
                if temp_bytes is not None or avatar_bytes_saved is not None or avatar_url is not None:
                    # El botón Quitar NO ejecuta el form submit, solo limpia el estado temporal y hace rerun
                    if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar."):
                        st.session_state["temp_avatar_bytes"] = None 
                        if "avatar_image" in st.session_state:
                            del st.session_state["avatar_image"]
                        if "avatar_url" in st.session_state:
                            del st.session_state["avatar_url"]
                        st.rerun() 
                        
            # --- INPUT: Nombre y Validación ---
            new_name = st.text_input("👤 Nombre completo", value=current_name, key="new_name")
            
            name_pattern = r"^[A-Za-zñÑáéíóúÁÉÍÓÚ\s]+$"
            if new_name and not re.match(name_pattern, new_name):
                st.error("❌ Error: El nombre no puede contener números ni caracteres especiales.")
                st.session_state["name_error"] = True
            else:
                st.session_state["name_error"] = False

            # --- INPUT: Teléfono y Validación ---
            new_phone = st.text_input("📞 Teléfono de contacto (9 dígitos, inicia con 9)", value=current_phone, max_chars=9, key="new_phone")

            if new_phone and not re.match(r"^9\d{8}$", new_phone):
                   st.error("❌ Error: El teléfono debe comenzar con '9' y contener exactamente 9 dígitos.")
                   st.session_state["phone_error"] = True
            else:
                st.session_state["phone_error"] = False
            
            # Determinar si el botón debe estar deshabilitado
            submit_button_disabled = st.session_state.get("name_error") or st.session_state.get("phone_error")


            # --- INPUT: Fecha de Nacimiento ---
            dob_value = None
            if current_dob_str:
                try:
                    dob_value = datetime.datetime.strptime(current_dob_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass
            
            new_dob = st.date_input("🗓️ Fecha de nacimiento", 
                                    value=dob_value or datetime.date(2000, 1, 1),
                                    min_value=datetime.date(1900, 1, 1), 
                                    max_value=datetime.date.today(),
                                    key="new_dob")
            
            # --- INPUT: Dirección ---
            new_address = st.text_area("🏠 Dirección (Opcional)", value=current_address, key="new_address")

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            
            # 1. Fecha de Creación (Solo fecha, sin hora)
            formatted_created = format_iso_date(
                st.session_state.get("created_at"), 
                date_only=True
            )
            # 2. Último Acceso (Fecha y hora en Perú, usa hora del sistema si es None)
            formatted_last_access = format_iso_date(
                st.session_state.get("last_sign_in_at"), 
                use_current_time_if_none=True,
                date_only=False
            )

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
                
                final_avatar_bytes = st.session_state.get("temp_avatar_bytes")
                
                if final_avatar_bytes is None and "temp_avatar_bytes" not in st.session_state:
                    final_avatar_bytes = st.session_state.get("avatar_image")
                
                update_user_profile(
                    new_name, 
                    new_dob, 
                    new_phone, 
                    new_address, 
                    final_avatar_bytes, 
                    user_id, 
                    supabase_client 
                )

    # Botón de cambio de contraseña fuera del form
    st.markdown("---")
    if st.button("🔒 Cambiar Contraseña", use_container_width=True):
        request_password_reset_callback(st.session_state.get("user_email"))



