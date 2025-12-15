import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re 

# -------------------------------------------------------------------
# --- NOTA IMPORTANTE: Inicialización de st.session_state ---
# -------------------------------------------------------------------
# Estos valores DEBEN ser inicializados por tu lógica de login/carga de perfil 
# si deseas que el formulario funcione sin errores. 
# Si no existen, se usarán los valores por defecto seguros (ej: "" o None).

if "user_id" not in st.session_state:
    # Inicialización segura de las claves necesarias para evitar KeyErrors
    st.session_state["user_id"] = None
    st.session_state["full_name"] = ""
    st.session_state["date_of_birth"] = None # Usar None para fecha si no está cargada
    st.session_state["phone_number"] = ""
    st.session_state["address"] = ""
    st.session_state["avatar_image"] = None 
    st.session_state["avatar_url"] = None 
    st.session_state["user_email"] = "N/A"
    st.session_state["user_role"] = "guest"
    # Campos que vendrían de Supabase Auth
    st.session_state["created_at"] = None 
    st.session_state["last_sign_in_at"] = None
    # Estados de validación y avatar temporal
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
        
        # Limpiar estados guardados para que el display use el temporal
        if "avatar_image" in st.session_state:
            del st.session_state["avatar_image"]
        if "avatar_url" in st.session_state:
            del st.session_state["avatar_url"]
        
    

# --- FUNCIÓN DE ACTUALIZACIÓN ---
def update_user_profile(new_name: str, new_dob: datetime.date, new_phone: str, new_address: str, avatar_bytes: Optional[bytes], user_id: str, supabase):
    """Actualiza datos si pasan las validaciones."""
    data_to_update = {}

    # Doble chequeo de errores antes de proceder al guardado
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
        # Asegurarse de que el avatar se guarda como base64 o se sube al storage
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        data_to_update["avatar_url"] = avatar_base64
        st.session_state["avatar_image"] = avatar_bytes 
            
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        # Si se eliminó la foto
        data_to_update["avatar_url"] = None
        st.session_state["avatar_image"] = None 

    if data_to_update:
        try:
            # --- Aquí iría la lógica real de Supabase.update() ---
            # Por ejemplo: supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            
            # Actualización del estado (Simulación local de éxito)
            st.session_state.update({k: v for k, v in data_to_update.items()})
            
            # Limpiar el estado temporal después de un guardado exitoso
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
# === 2. RENDERIZADO CON VALIDACIONES Y LECTURA DE ESTADO          ===
# ====================================================================

def render_profile_page(supabase, request_password_reset):
    """Renderiza el perfil del usuario con validaciones de entrada."""
    user_id = st.session_state.get("user_id")
    
    # Obtener valores actuales del estado de la sesión (usando valores seguros por defecto)
    current_name = st.session_state.get("full_name", "")
    current_dob_str = st.session_state.get("date_of_birth")
    current_phone = st.session_state.get("phone_number", "") 
    current_address = st.session_state.get("address", "")
    
    # Datos para el Avatar
    avatar_bytes_saved = st.session_state.get("avatar_image")
    avatar_url = st.session_state.get("avatar_url", None)
    temp_bytes = st.session_state.get("temp_avatar_bytes")

    if not user_id:
        st.warning("⚠️ No se pudo cargar el ID del usuario. Por favor, inicia sesión para editar.")
        # Podemos mostrar un formulario vacío o solo lectura si no hay ID
        return

    col_avatar, col_details = st.columns([1, 2])

    with col_details:
        st.header("Datos Personales y de Cuenta")
        
        # Inicializar la bandera de error del formulario (False por defecto)
        form_has_error = False

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
                        
            # 2. Campos de datos personales (Columna Derecha)
            
            # --- INPUT: Nombre y Validación ---
            new_name = st.text_input("👤 Nombre completo", value=current_name, key="new_name")
            
            name_pattern = r"^[A-Za-zñÑáéíóúÁÉÍÓÚ\s]+$"
            if new_name and not re.match(name_pattern, new_name):
                st.error("❌ Error: El nombre no puede contener números ni caracteres especiales.")
                st.session_state["name_error"] = True
                form_has_error = True # Activa la bandera para deshabilitar el botón
            else:
                st.session_state["name_error"] = False

            # --- INPUT: Teléfono y Validación ---
            new_phone = st.text_input("📞 Teléfono de contacto (9 dígitos, inicia con 9)", value=current_phone, max_chars=9, key="new_phone")

            if new_phone and not re.match(r"^9\d{8}$", new_phone):
                 st.error("❌ Error: El teléfono debe comenzar con '9' y contener exactamente 9 dígitos.")
                 st.session_state["phone_error"] = True
                 form_has_error = True # Activa la bandera para deshabilitar el botón
            else:
                st.session_state["phone_error"] = False

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
            
            # --- Formateo de Fechas Reales (Lee del estado, si está cargado) ---
            
            def format_iso_date(iso_string):
                """Formatea un string ISO 8601 a un formato legible."""
                if not iso_string:
                    return "N/A (No cargado)"
                try:
                    # Reemplaza 'Z' para compatibilidad con datetime.fromisoformat
                    dt = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
                    return dt.strftime("%Y-%m-%d %H:%M hrs")
                except (ValueError, TypeError):
                    return "N/A (Error de formato)"

            formatted_created = format_iso_date(st.session_state.get("created_at"))
            formatted_last_access = format_iso_date(st.session_state.get("last_sign_in_at"))


            col_left, col_right = st.columns(2)
            with col_left:
                st.text_input("📅 Fecha de Creación", value=formatted_created, disabled=True, 
                              help="Momento en que la cuenta de usuario fue registrada.")
            with col_right:
                st.text_input("⏰ Último Acceso", value=formatted_last_access, disabled=True,
                              help="Última vez que el usuario inició sesión correctamente.")
            
            st.text_input("🏷️ Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("📧 Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Botón de Guardar
            submit_button_disabled = form_has_error # Deshabilitar si la bandera es True
            
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
                    MockSupabase() # Usamos el Mock/Objeto real de Supabase aquí
                )

    # Botón de cambio de contraseña fuera del form
    st.markdown("---")
    if st.button("🔒 Cambiar Contraseña", use_container_width=True):
        request_password_reset(st.session_state.get("user_email"))

# -------------------------------------------------------------------
# --- CÓDIGO DE EJECUCIÓN Y SIMULACIÓN DE DEPENDENCIAS (PARA PROBAR) ---
# -------------------------------------------------------------------

# Estas clases son necesarias para que el código corra sin errores 
# si no tienes implementadas las clases reales de Supabase y el reseteo.
class MockSupabase:
    def table(self, table_name): return self
    def update(self, data): return self
    def eq(self, column, value): return self
    def execute(self): pass

def mock_request_password_reset(email):
    st.success(f"📧 Simulación: Se ha enviado un enlace de restablecimiento de contraseña a {email}.")

if __name__ == '__main__':
    st.set_page_config(layout="wide")
    # Para la prueba inicial, puedes establecer algunos datos de prueba manualmente aquí:
    st.session_state["user_id"] = "test_user_123" 
    st.session_state["full_name"] = "Usuario Test"
    st.session_state["phone_number"] = "900000000"
    st.session_state["created_at"] = "2024-05-01T10:00:00.000Z"
    st.session_state["last_sign_in_at"] = "2025-12-15T07:55:00.000Z"
    
    render_profile_page(MockSupabase(), mock_request_password_reset)



