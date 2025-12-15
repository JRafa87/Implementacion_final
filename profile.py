import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re 

# -------------------------------------------------------------------
# --- INICIALIZACIÓN DE st.session_state (Necesario para el código) ---
# -------------------------------------------------------------------

if "user_id" not in st.session_state:
    st.session_state["user_id"] = "test_user_123" 
    st.session_state["full_name"] = "Usuario Test"
    st.session_state["date_of_birth"] = "2000-01-01" # Inicialización con string para la fecha
    st.session_state["phone_number"] = "900000000"
    st.session_state["address"] = "Dirección de Prueba"
    st.session_state["avatar_image"] = None 
    st.session_state["avatar_url"] = None 
    st.session_state["user_email"] = "prueba@ejemplo.com"
    st.session_state["user_role"] = "guest"
    st.session_state["created_at"] = "2024-05-01T10:00:00.000Z"
    st.session_state["last_sign_in_at"] = "2025-12-15T07:55:00.000Z"
    st.session_state["temp_avatar_bytes"] = None
    st.session_state["name_error"] = False
    st.session_state["phone_error"] = False

# ====================================================================
# === 1. FUNCIÓN CALLBACK PARA MANEJAR SUBIDA DE ARCHIVO             ===
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

# --- FUNCIÓN DE ACTUALIZACIÓN ---
def update_user_profile(new_name: str, new_dob: datetime.date, new_phone: str, new_address: str, avatar_bytes: Optional[bytes], user_id: str, supabase):
    """Actualiza datos si pasan las validaciones."""
    data_to_update = {}

    if st.session_state.get("name_error") or st.session_state.get("phone_error"):
        st.error("❌ Por favor, corrige los errores de validación antes de guardar.")
        return

    # Se usan los valores que están en st.session_state (actualizados por los inputs externos)
    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name
    if new_phone != st.session_state.get("phone_number"):
        data_to_update["phone_number"] = new_phone
    if new_address != st.session_state.get("address"):
        data_to_update["address"] = new_address

    dob_str = new_dob.strftime("%Y-%m-%d") if new_dob else None
    current_dob_str = st.session_state.get("date_of_birth")
    if dob_str != current_dob_str:
        data_to_update["date_of_birth"] = dob_str 

    # Manejo del Avatar
    if avatar_bytes is not None and avatar_bytes != st.session_state.get("avatar_image"):
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        data_to_update["avatar_url"] = avatar_base64
        st.session_state["avatar_image"] = avatar_bytes 
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        data_to_update["avatar_url"] = None
        st.session_state["avatar_image"] = None 

    if data_to_update:
        try:
            # --- Lógica de Supabase.update() aquí ---
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
# === 2. RENDERIZADO CON VALIDACIONES DINÁMICAS Y ESTRUCTURA CORREGIDA ===
# ====================================================================

def format_iso_date(iso_string):
    """Formatea un string ISO 8601 a un formato legible."""
    if not iso_string:
        return "N/A (No cargado)"
    try:
        dt = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M hrs")
    except (ValueError, TypeError):
        return "N/A (Error de formato)"

def render_profile_page(supabase, request_password_reset):
    """Renderiza el perfil del usuario con validaciones de entrada dinámicas."""
    user_id = st.session_state.get("user_id")
    
    # Obtener valores actuales (desde st.session_state)
    current_name = st.session_state.get("full_name", "")
    current_phone = st.session_state.get("phone_number", "") 
    
    if not user_id:
        st.warning("⚠️ No se pudo cargar el ID del usuario.")
        return

    st.header("Datos Personales y de Cuenta")
    
    # -------------------------------------------------------------------------
    # --- 1. VALIDACIONES DINÁMICAS (FUERA DEL FORMULARIO PARA RERUN) ---
    # -------------------------------------------------------------------------
    
    # Nombre
    new_name = st.text_input("👤 Nombre completo", value=current_name, key="full_name_external")
    name_pattern = r"^[A-Za-zñÑáéíóúÁÉÍÓÚ\s]+$"
    if new_name and not re.match(name_pattern, new_name):
        st.error("❌ Error: El nombre no puede contener números ni caracteres especiales.")
        st.session_state["name_error"] = True
    else:
        st.session_state["name_error"] = False

    # Teléfono
    new_phone = st.text_input("📞 Teléfono de contacto (9 dígitos, inicia con 9)", value=current_phone, max_chars=9, key="phone_number_external")
    if new_phone and not re.match(r"^9\d{8}$", new_phone):
         st.error("❌ Error: El teléfono debe comenzar con '9' y contener exactamente 9 dígitos.")
         st.session_state["phone_error"] = True
    else:
        st.session_state["phone_error"] = False

    # Actualizamos el estado de error global
    form_has_error = st.session_state["name_error"] or st.session_state["phone_error"]
    
    # -------------------------------------------------------------------------
    # --- 2. EL FORMULARIO (CON EL RESTO DE WIDGETS Y EL BOTÓN DE ENVÍO) ---
    # -------------------------------------------------------------------------
    
    # Transferir los valores validados externamente al estado de sesión para el guardado:
    st.session_state["full_name"] = new_name
    st.session_state["phone_number"] = new_phone

    with st.form("profile_form", clear_on_submit=False):
        
        col_avatar, col_details = st.columns([1, 2])
        
        # --- COLUMNA IZQUIERDA: AVATAR ---
        with col_avatar:
            st.subheader("Foto de Perfil")
            
            # Lógica de display del avatar
            temp_bytes = st.session_state.get("temp_avatar_bytes")
            avatar_bytes_saved = st.session_state.get("avatar_image")
            avatar_url = st.session_state.get("avatar_url", None)

            if temp_bytes is not None:
                display_image = temp_bytes 
            elif avatar_bytes_saved is not None:
                display_image = avatar_bytes_saved
            elif avatar_url is not None:
                display_image = avatar_url
            else:
                display_image = "https://placehold.co/200x200/A0A0A0/ffffff?text=U"
                    
            st.image(display_image, width=150)
            
            st.file_uploader(
                "Subir/Cambiar Foto", 
                type=["png","jpg","jpeg"], 
                key="avatar_uploader_widget", 
                on_change=handle_file_upload 
            )
            
            if temp_bytes is not None or avatar_bytes_saved is not None or avatar_url is not None:
                if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar."):
                    st.session_state["temp_avatar_bytes"] = None 
                    if "avatar_image" in st.session_state:
                        del st.session_state["avatar_image"]
                    if "avatar_url" in st.session_state:
                        del st.session_state["avatar_url"]
                    st.rerun() 
                    
        # --- COLUMNA DERECHA: DATOS RESTANTES ---
        with col_details:
            
            st.markdown("---") # Separador visual

            # --- INPUT: Fecha de Nacimiento ---
            current_dob_str = st.session_state.get("date_of_birth")
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
            current_address = st.session_state.get("address", "")
            new_address = st.text_area("🏠 Dirección (Opcional)", value=current_address, key="new_address")

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            
            # Datos de Cuenta
            formatted_created = format_iso_date(st.session_state.get("created_at"))
            formatted_last_access = format_iso_date(st.session_state.get("last_sign_in_at"))

            col_account_left, col_account_right = st.columns(2)
            with col_account_left:
                st.text_input("📅 Fecha de Creación", value=formatted_created, disabled=True)
            with col_account_right:
                st.text_input("⏰ Último Acceso", value=formatted_last_access, disabled=True)
            
            st.text_input("🏷️ Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("📧 Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Botón de Guardar (¡Asegurado dentro del st.form!)
            if st.form_submit_button("💾 Guardar Cambios", disabled=form_has_error):
                
                final_avatar_bytes = st.session_state.get("temp_avatar_bytes")
                
                if final_avatar_bytes is None and "temp_avatar_bytes" not in st.session_state:
                    final_avatar_bytes = st.session_state.get("avatar_image")
                
                # Pasamos los valores del estado de la sesión (actualizados por los inputs externos)
                update_user_profile(
                    st.session_state["full_name"], 
                    new_dob, 
                    st.session_state["phone_number"], 
                    new_address, 
                    final_avatar_bytes, 
                    user_id, 
                    MockSupabase() 
                )

    # Botón de cambio de contraseña (Fuera del form)
    st.markdown("---")
    if st.button("🔒 Cambiar Contraseña", use_container_width=True):
        request_password_reset(st.session_state.get("user_email"))

# -------------------------------------------------------------------
# --- CÓDIGO DE EJECUCIÓN Y SIMULACIÓN DE DEPENDENCIAS ---
# -------------------------------------------------------------------

class MockSupabase:
    def table(self, table_name): return self
    def update(self, data): return self
    def eq(self, column, value): return self
    def execute(self): pass

def mock_request_password_reset(email):
    st.success(f"📧 Simulación: Se ha enviado un enlace de restablecimiento de contraseña a {email}.")

if __name__ == '__main__':
    st.set_page_config(layout="wide")
    render_profile_page(MockSupabase(), mock_request_password_reset)



