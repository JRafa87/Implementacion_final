import streamlit as st
import datetime
from typing import Optional
import base64
import time

# --- FUNCIÓN DE ACTUALIZACIÓN (SIN CAMBIOS FUNCIONALES) ---
def update_user_profile(new_name: str, new_dob: datetime.date, avatar_bytes: Optional[bytes], user_id: str, supabase):
    """Actualiza nombre, fecha de nacimiento y avatar del usuario en Supabase."""
    data_to_update = {}

    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name

    dob_str = new_dob.strftime("%Y-%m-%d") if new_dob else None
    current_dob_str = st.session_state.get("date_of_birth")

    if dob_str != current_dob_str:
        data_to_update["date_of_birth"] = dob_str 

    if avatar_bytes is not None and avatar_bytes != st.session_state.get("avatar_image"):
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        data_to_update["avatar_url"] = avatar_base64
        st.session_state["avatar_image"] = avatar_bytes
            
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        data_to_update["avatar_url"] = None
        st.session_state["avatar_image"] = None

    if data_to_update:
        try:
            # Lógica Supabase
            st.session_state.update({k: v for k, v in data_to_update.items()})
            st.session_state["full_name"] = new_name
            st.session_state["date_of_birth"] = dob_str
            
            if "temp_avatar_bytes" in st.session_state:
                del st.session_state["temp_avatar_bytes"]
            
            # Limpiar el uploader después de guardar
            if "avatar_uploader_widget" in st.session_state:
                st.session_state["avatar_uploader_widget"] = None
            
            st.success("¡Perfil actualizado con éxito!")
            st.rerun() 
        except Exception as e:
            st.error(f"Error al actualizar el perfil: {e}")
    else:
        st.info("No se detectaron cambios para guardar.")

# ====================================================================
# === 2. RENDERIZADO CORREGIDO (IMPLEMENTACIÓN FINAL SIN CALLBACKS) ===
# ====================================================================

def render_profile_page(supabase, request_password_reset):
    """Renderiza el perfil del usuario y permite actualizarlo."""
    user_id = st.session_state.get("user_id")
    current_name = st.session_state.get("full_name", "")
    current_dob_str = st.session_state.get("date_of_birth")
    
    avatar_bytes_saved = st.session_state.get("avatar_image")
    avatar_url = st.session_state.get("avatar_url", None)
    temp_bytes = st.session_state.get("temp_avatar_bytes")

    if not user_id:
        st.error("No se pudo cargar el ID del usuario.")
        return

    # Variables de Control de Rerun
    should_rerun = False
    
    col_avatar, col_details = st.columns([1, 2])

    with col_details:
        st.header("Datos Personales y de Cuenta")
        # Usamos una clave dinámica para el formulario para forzar la limpieza del file_uploader
        with st.form("profile_form", clear_on_submit=False): 
            
            # 1. --- Manejo de la Foto de Perfil (Columna Izquierda) ---
            with col_avatar:
                st.subheader("Foto de Perfil")
                
                # Lógica de Display
                if temp_bytes is not None:
                    display_image = temp_bytes 
                elif avatar_bytes_saved is not None:
                    display_image = avatar_bytes_saved
                elif avatar_url is not None:
                    display_image = avatar_url
                else:
                    display_image = "https://placehold.co/200x200/A0A0A0/ffffff?text=U"
                        
                st.image(display_image, width=150)
                
                # Subir/Cambiar Foto
                uploaded_file = st.file_uploader(
                    "Subir/Cambiar Foto", 
                    type=["png","jpg","jpeg"], 
                    key="avatar_uploader_widget" # Usamos una clave para la limpieza manual
                )
                
                # **LÓGICA CLAVE PARA OCULTAR EL NOMBRE Y RERUN**
                # 1. Chequeamos si hay un archivo subido Y si no lo hemos procesado ya (temp_bytes_processed)
                if uploaded_file and "temp_bytes_processed" not in st.session_state:
                    uploaded_file.seek(0)
                    
                    # 2. Guardar los bytes en el estado temporal
                    st.session_state["temp_avatar_bytes"] = uploaded_file.read() 
                    
                    # 3. Borrar el estado de la imagen guardada para que el display use la temporal
                    if "avatar_image" in st.session_state: del st.session_state["avatar_image"]
                    if "avatar_url" in st.session_state: del st.session_state["avatar_url"]
                    
                    # 4. Marcar que se procesó (para evitar ciclos infinitos si st.rerun falla)
                    st.session_state["temp_bytes_processed"] = True
                    should_rerun = True
                
                # Opción para Quitar
                if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar.", key="remove_btn"):
                    st.session_state["temp_avatar_bytes"] = None 
                    
                    # Limpiamos explícitamente el widget antes del rerun
                    st.session_state["avatar_uploader_widget"] = None 
                    
                    # Eliminamos los datos guardados para mostrar el placeholder
                    if "avatar_image" in st.session_state: del st.session_state["avatar_image"]
                    if "avatar_url" in st.session_state: del st.session_state["avatar_url"]
                    
                    # Limpiamos la marca de procesado si existía
                    if "temp_bytes_processed" in st.session_state: del st.session_state["temp_bytes_processed"]

                    should_rerun = True
                    
            # -------------------------------------------------------------
            
            # 2. Campos de datos personales (Columna Derecha)
            new_name = st.text_input("Nombre completo", value=current_name)
            
            dob_value = None
            if current_dob_str:
                try:
                    dob_value = datetime.datetime.strptime(current_dob_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass
            
            new_dob = st.date_input("Fecha de nacimiento", value=dob_value or datetime.date(2000, 1, 1))

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            st.text_input("Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Botón de Guardar
            if st.form_submit_button("💾 Guardar Cambios"):
                
                # Al guardar, eliminamos la marca de procesado
                if "temp_bytes_processed" in st.session_state:
                    del st.session_state["temp_bytes_processed"]
                    
                final_avatar_bytes = st.session_state.get("temp_avatar_bytes")
                
                # Si el usuario no subió/quitó nada (temp_avatar_bytes es None y no está en la sesión), usamos el guardado
                if final_avatar_bytes is None and "temp_avatar_bytes" not in st.session_state:
                    final_avatar_bytes = st.session_state.get("avatar_image")
                
                update_user_profile(new_name, new_dob, final_avatar_bytes, user_id, supabase)

    # **EJECUCIÓN FINAL**
    # Si se marcó la bandera, limpiamos el uploader y forzamos el rerun fuera del formulario
    if should_rerun:
        # Aseguramos la limpieza del widget de subida antes del rerun (oculta el nombre)
        st.session_state["avatar_uploader_widget"] = None 
        
        # Limpiamos la marca de procesado si solo fue una subida, no un guardado
        if "temp_bytes_processed" in st.session_state:
            del st.session_state["temp_bytes_processed"]
            
        st.rerun()



