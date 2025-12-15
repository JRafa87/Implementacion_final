import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re 

# -------------------------------------------------------------------
# --- INICIALIZACIÓN DE st.session_state (Sin Simulación de Datos) ---
# -------------------------------------------------------------------

if "user_id" not in st.session_state:
    st.session_state["user_id"] = "test_user_123" # ID de prueba para que el formulario se muestre
    st.session_state["full_name"] = "Usuario Test"
    st.session_state["date_of_birth"] = None 
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
    """
    Maneja la subida de un archivo y guarda los bytes temporalmente.
    """
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

    # Si la validación en el scope global falló, detenemos la actualización
    if st.session_state.get("name_error") or st.session_state.get("phone_error"):
        st.error("❌ Por favor, corrige los errores de validación antes de guardar.")
        return

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
            # --- Aquí iría la lógica real de Supabase.update() ---
            
            # Actualización del estado (Simulación local de éxito)
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
# === 2. RENDERIZADO CON VALIDACIONES DINÁMICAS (FUERA DEL FORM) ===
# ====================================================================

def render_profile_page(supabase, request_password_reset):
    """Renderiza el perfil del usuario con validaciones de entrada dinámicas."""
    user_id = st.session_state.get("user_id")
    
    current_name = st.session_state.get("full_name", "")
    current_dob_str = st.session_state.get("date_of_birth")
    current_phone = st.session_state.get("phone_number", "") 
    current_address = st.session_state.get("address", "")
    
    avatar_bytes_saved = st.session_state.get("avatar_image")
    avatar_url = st.session_state.get("avatar_url", None)
    temp_bytes = st.session_state.get("temp_avatar_bytes")

    if not user_id:
        st.warning("⚠️ No se pudo cargar el ID del usuario. Por favor, inicia sesión para editar.")
        return

    st.header("Datos Personales y de Cuenta")
    
    # --- VALIDACIONES DINÁMICAS (FUERA DEL FORMULARIO) ---
    col_left_inputs, col_right_inputs = st.columns([1, 2])
    
    with col_right_inputs:
        
        # --- INPUT: Nombre y Validación ---
        # Usamos el key 'full_name' para que se actualice el estado directamente
        new_name = st.text_input("👤 Nombre completo", value=current_name, key="full_name")
        
        name_pattern = r"^[A-Za-zñÑáéíóúÁÉÍÓÚ\s]+$"
        if new_name and not re.match(name_pattern, new_name):
            st.error("❌ Error: El nombre no puede contener números ni caracteres especiales.")
            st.session_state["name_error"] = True
        else:
            st.session_state["name_error"] = False

        # --- INPUT: Teléfono y Validación ---
        # Usamos el key 'phone_number'
        new_phone = st.text_input("📞 Teléfono de contacto (9 dígitos, inicia con 9)", value=current_phone, max_chars=9, key="phone_number")

        if new_phone and not re.match(r"^9\d{8}$", new_phone):
             st.error("❌ Error: El teléfono debe comenzar con '9' y contener exactamente 9 dígitos.")
             st.session_state["phone_error"] = True
        else:
            st.session_state["phone_error"] = False

    # Actualizamos el estado de error global
    form_has_error = st.session_state["name_error"] or st.session_state["phone_error"]
    
    # ------------------------------------------------------
    
    # --- COMIENZA EL FORMULARIO (PARA LOS CAMPOS QUE NO NECESITAN VALIDACIÓN DINÁMICA) ---
    col_avatar, col_details = st.columns([1, 2])
    
    with st.form("profile_form", clear_on_submit=False):
        
        # 1. --- Manejo de la Foto de Perfil (Columna Izquierda) ---
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
                if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar."):
                    st.session_state["temp_avatar_bytes"] = None 
                    if "avatar_image" in st.session_state:
                        del st.session_state["avatar_image"]
                    if "avatar_url" in st.session_state:
                        del st.session_state["avatar_url"]
                    st.rerun() 

        # 2. Campos de datos personales restantes (Columna Derecha)
        with col_details:
            
            # Colocamos los inputs de nombre y teléfono de nuevo aquí como marcadores
            # para mantener la estructura visual, pero deshabilitados.
            st.text_input("👤 Nombre completo", value=st.session_state["full_name"], disabled=True, help="Edite este campo arriba.")
            st.text_input("📞 Teléfono de contacto", value=st.session_state["phone_number"], disabled=True, help="Edite este campo arriba.")
            
            # --- INPUT: Fecha de Nacimiento (Dentro del form) ---
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
            
            # --- INPUT: Dirección (Dentro del form) ---
            new_address = st.text_area("🏠 Dirección (Opcional)", value=current_address, key="new_address")

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            
            # --- Formateo de Fechas Reales ---
            
            def format_iso_date(iso_string):
                """Formatea un string ISO 8601 a un formato legible."""
                if not iso_string:
                    return "N/A (No cargado)"
                try:
                    dt = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
                    return dt.strftime("%Y-%m-%d %H:%M hrs")
                except (ValueError, TypeError):
                    return "N/A (Error de formato)"

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
            
            # 3. Botón de Guardar
            if st.form_submit_button("💾 Guardar Cambios", disabled=form_has_error):
                
                final_avatar_bytes = st.session_state.get("temp_avatar_bytes")
                
                if final_avatar_bytes is None and "temp_avatar_bytes" not in st.session_state:
                    final_avatar_bytes = st.session_state.get("avatar_image")
                
                # Usamos los valores del estado de la sesión, que fueron actualizados por los inputs de arriba
                update_user_profile(
                    st.session_state["full_name"], # <--- Usamos el valor del estado global
                    new_dob, 
                    st.session_state["phone_number"], # <--- Usamos el valor del estado global
                    new_address, 
                    final_avatar_bytes, 
                    user_id, 
                    MockSupabase()
                )

    # Botón de cambio de contraseña fuera del form
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



